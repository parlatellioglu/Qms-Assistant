// App — orchestrates the QMS Assistant, wired to the live POST /chat API.
// /chat runs chunked retrieval + the LLM answer (the ask_cmmi --chunked --answer
// flow) and returns { query, answer, results:[{id,title,document_type,department,
// author,version,status,created_date,tags,similarity_score,content,excerpt}] }.
const { ChatComposer, IconButton, SourceDrawer, Badge } = window.QMSDesignSystem;
const { SUGGESTIONS, KB_LABEL, ROLES } = window.QMS_CONFIG;
const ROLE_LIST = ROLES || [{ id: 'genel', label: 'Genel', suggestions: SUGGESTIONS }];
const History = window.QMS_History;

let _id = 100;
const nid = () => 'm' + (++_id);

const clamp01 = (x) => Math.max(0, Math.min(1, x));

// Parse one SSE frame ("event: x\ndata: {...}") into { event, data }.
function parseSSE(frame) {
  let event = 'message';
  let data = '';
  frame.split('\n').forEach((line) => {
    if (line.startsWith('event:')) event = line.slice(6).trim();
    else if (line.startsWith('data:')) data += line.slice(5).trim();
  });
  if (!data) return null;
  try { return { event, data: JSON.parse(data) }; } catch (e) { return null; }
}

// Map one /chat source result to the shape SourceCard + SourceDrawer consume.
function toSourceDoc(r) {
  const content = r.content || '';
  // CMMI parent chunks are line-oriented (paragraphs/table rows on single \n),
  // so split per line into drawer paragraphs rather than on blank lines.
  const body = content.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  const excerpt = r.excerpt || (content ? content.slice(0, 320) : undefined);
  return {
    docId: r.id,
    title: r.title,
    docType: r.document_type,
    // chunked relevance can aggregate above 1; clamp for the 0–1 score pill.
    score: (r.similarity_score != null) ? clamp01(r.similarity_score) : undefined,
    snippet: excerpt,   // SourceCard collapsed text
    excerpt: excerpt,   // SourceDrawer highlighted excerpt
    body: body.length ? body : (content ? [content] : []),
    owner: r.department,
    status: r.status,
    revision: r.version ? ('Rev. ' + r.version) : undefined,
    effective: r.created_date,
  };
}

function PanelIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M15 4v16" /></svg>
  );
}

function App() {
  const [activeId, setActiveId] = React.useState(null);
  const [messages, setMessages] = React.useState([]);
  const [docsById, setDocsById] = React.useState({});
  const [input, setInput] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [busyLabel, setBusyLabel] = React.useState('Searching documents');
  const [openDoc, setOpenDoc] = React.useState(null);
  const [cfg, setCfg] = React.useState(null); // backend runtime config (model, params)
  const [streamingId, setStreamingId] = React.useState(null); // id of the answer being streamed
  const [view, setView] = React.useState('chat'); // 'chat' | 'project' | 'compliance' | 'rules'
  // Selected role (soft personalization): tailors the empty-state starter questions.
  // Persisted locally; defaults to 'genel'. Retrieval is unaffected — all roles
  // still search every document.
  const [role, setRole] = React.useState(() => {
    try { return localStorage.getItem('kka_role') || 'genel'; } catch (e) { return 'genel'; }
  });
  React.useEffect(() => {
    try { localStorage.setItem('kka_role', role); } catch (e) { /* private mode: ignore */ }
  }, [role]);
  const roleObj = ROLE_LIST.find((r) => r.id === role) || ROLE_LIST[0];
  const roleSuggestions = (roleObj && roleObj.suggestions) || SUGGESTIONS;

  const scrollRef = React.useRef(null);
  const timers = React.useRef([]);
  // Whether the view is pinned to the bottom. Auto-scroll only follows new content
  // while pinned, so scrolling up mid-stream to re-read an earlier message isn't
  // yanked back down on the next streamed token.
  const atBottomRef = React.useRef(true);
  const lastTopRef = React.useRef(0); // previous scrollTop, to detect scroll direction

  // Rolling conversation summary (see /summarize). Held in refs, not state: it's
  // sent to the backend with each question but never rendered, so it shouldn't
  // trigger re-renders. `summarizedCount` = how many turns are already folded in,
  // so each regen sends only the new turns (incremental — cost stays flat).
  const summaryRef = React.useRef('');
  const summarizedCountRef = React.useRef(0);
  const lastSummarizedTurnRef = React.useRef(0); // guards one regen per boundary

  // Persisted chat history (local SQLite on the backend, via window.QMS_History). The
  // sidebar list is state; the current conversation's id is a ref (used inside
  // async handlers, and it shouldn't trigger re-renders).
  const [conversations, setConversations] = React.useState([]);
  const convIdRef = React.useRef(null);
  // Set true when we hydrate an existing thread, so the persist effect below skips
  // the save it would otherwise fire on the resulting messages change. Opening a
  // chat to read it must not touch updated_at — only sending a message should.
  const skipNextSaveRef = React.useRef(false);
  React.useEffect(() => { if (History) History.list().then(setConversations); }, []);

  // Unpin on ANY upward scroll (direction-based, not a distance threshold — a small
  // scroll-up near the bottom must still release, or streaming keeps yanking back).
  // Re-pin only once the user is essentially at the very bottom again.
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const dist = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (el.scrollTop < lastTopRef.current - 2) atBottomRef.current = false; // scrolled up
    else if (dist < 8) atBottomRef.current = true;                          // reached bottom
    lastTopRef.current = el.scrollTop;
  };

  React.useEffect(() => {
    if (atBottomRef.current && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, busy]);

  React.useEffect(() => () => timers.current.forEach(clearTimeout), []);

  // Pull runtime config (which model, retrieval params) to show in the UI.
  React.useEffect(() => {
    fetch((window.QMS_CONFIG.API_BASE || '') + '/config')
      .then((r) => r.ok ? r.json() : null)
      .then((c) => c && setCfg(c))
      .catch(() => {});
  }, []);

  function newChat() {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    summaryRef.current = '';
    summarizedCountRef.current = 0;
    lastSummarizedTurnRef.current = 0;
    convIdRef.current = null;
    setBusy(false); setOpenDoc(null); setMessages([]); setActiveId(null);
  }

  // Reopen a stored conversation: hydrate messages, source docs and the rolling
  // summary so a resumed chat keeps its context (and its next question still
  // carries the summary). Guarding lastSummarizedTurn to the loaded turn count
  // stops the background summarizer from re-firing the moment it loads.
  async function openConversation(id) {
    if (!History) return;
    const data = await History.load(id);
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setBusy(false); setOpenDoc(null); setStreamingId(null);
    if (!data) { newChat(); History.list().then(setConversations); return; }
    convIdRef.current = id;
    summaryRef.current = data.summary || '';
    summarizedCountRef.current = data.summarizedCount || 0;
    lastSummarizedTurnRef.current = (data.messages || []).filter((m) => m.role === 'user').length;
    atBottomRef.current = true;
    // Hydrating state below triggers the persist effect; suppress its save so a
    // read-only open doesn't rewrite updated_at (which would move the chat to today).
    skipNextSaveRef.current = true;
    setDocsById((prev) => ({ ...prev, ...(data.docsById || {}) }));
    setMessages(data.messages || []);
    setActiveId(id);
  }

  async function deleteConversation(id) {
    if (!History) return;
    if (!window.confirm('Delete this chat?')) return;
    await History.remove(id);
    if (convIdRef.current === id) newChat();
    History.list().then(setConversations);
  }

  async function send(text) {
    text = (text || '').trim();
    if (!text || busy) return;
    setInput('');
    // Recent turns of THIS conversation (before adding the new question), so the
    // backend can resolve follow-ups like "results of those tests". `messages` is
    // the pre-send array here (state update below is async). We send a generous raw
    // window; the backend selects what to keep (many user turns, few assistant
    // answers, under a char budget). The cap comes from /config so one env var
    // drives it; 40 is the fallback.
    const rawCap = (cfg && cfg.history_raw_cap) || 40;
    const history = messages
      .filter((msg) => (msg.role === 'user' || msg.role === 'assistant') && (msg.text || '').trim())
      .slice(-rawCap)
      .map((msg) => ({ role: msg.role, content: msg.text }));
    // First question of a fresh thread mints a conversation id (used as the
    // storage key and the sidebar's active highlight). Continuing a thread keeps
    // the existing id, so the save effect updates the same record.
    if (History && !convIdRef.current) {
      convIdRef.current = History.newId();
      setActiveId(convIdRef.current);
    }
    // Sending a new question re-pins to the bottom, even if the user had scrolled up.
    atBottomRef.current = true;
    setMessages((m) => [...m, { id: nid(), role: 'user', text }]);
    setBusy(true);
    setBusyLabel('Searching documents');

    const asstId = nid();
    const errText = 'The assistant could not be reached. Check that the API, Qdrant, and Ollama are running, then try again.';
    const setMsg = (id, patch) => setMessages((m) => m.map((msg) => msg.id === id ? { ...msg, ...patch } : msg));

    try {
      const resp = await fetch((window.QMS_CONFIG.API_BASE || '') + '/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text, history, summary: summaryRef.current }),
      });
      if (!resp.ok || !resp.body) throw new Error('HTTP ' + resp.status);

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      let started = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let nl;
        while ((nl = buf.indexOf('\n\n')) >= 0) {
          const frame = buf.slice(0, nl);
          buf = buf.slice(nl + 2);
          const ev = parseSSE(frame);
          if (!ev) continue;

          if (ev.event === 'meta') {
            const results = Array.isArray(ev.data.results) ? ev.data.results : [];
            const docs = {}; const ids = [];
            results.forEach((r) => { const d = toSourceDoc(r); docs[d.docId] = d; ids.push(d.docId); });
            setDocsById((prev) => ({ ...prev, ...docs }));
            setBusyLabel('Generating answer' + (cfg && cfg.model ? ' · ' + cfg.model : ''));
            setMessages((m) => [...m, {
              id: asstId, role: 'assistant', time: 'just now',
              text: '', sources: ids, meta: ev.data.meta || null, streaming: true,
            }]);
            setStreamingId(asstId);
            started = true;
          } else if (ev.event === 'token') {
            setMessages((m) => m.map((msg) => msg.id === asstId ? { ...msg, text: msg.text + (ev.data.text || '') } : msg));
          } else if (ev.event === 'done') {
            setMsg(asstId, { streaming: false });
            setMessages((m) => m.map((msg) => msg.id === asstId
              ? { ...msg, streaming: false, meta: { ...(msg.meta || {}), generation_ms: ev.data.generation_ms, total_ms: ev.data.total_ms } }
              : msg));
          } else if (ev.event === 'error') {
            if (started) setMsg(asstId, { text: ev.data.message || 'Could not generate an answer.', streaming: false });
            else setMessages((m) => [...m, { id: asstId, role: 'assistant', time: 'just now', text: ev.data.message || 'Could not generate an answer.', sources: [] }]);
          }
        }
      }
      // Stream ended without an explicit error but produced no answer.
      setMessages((m) => m.map((msg) => (msg.id === asstId && !msg.text) ? { ...msg, text: errText, streaming: false } : msg));
    } catch (err) {
      setMessages((m) => {
        if (m.some((msg) => msg.id === asstId)) return m.map((msg) => msg.id === asstId ? { ...msg, text: msg.text || errText, streaming: false } : msg);
        return [...m, { id: asstId, role: 'assistant', time: 'just now', text: errText, sources: [] }];
      });
    } finally {
      setBusy(false);
      setStreamingId(null);
    }
  }

  // Rolling summary: after a turn finishes (not mid-stream), regenerate the
  // "what this chat is about" block every N user turns, once the chat is long
  // enough. Runs in the background — the answer already streamed, and the summary
  // is only needed on the NEXT question, so this adds no visible latency. Only the
  // turns since the last fold are sent, so the cost stays flat as the chat grows.
  React.useEffect(() => {
    if (busy) return;
    const everyTurns = (cfg && cfg.summary_every_turns) || 4;
    const minTurns = (cfg && cfg.summary_min_turns) || 12;
    const convo = messages.filter((m) => (m.role === 'user' || m.role === 'assistant') && (m.text || '').trim());
    if (convo.length < minTurns) return;
    const userTurns = convo.filter((m) => m.role === 'user').length;
    if (userTurns === 0 || userTurns % everyTurns !== 0) return;
    if (lastSummarizedTurnRef.current === userTurns) return; // already done at this boundary
    const newTurns = convo.slice(summarizedCountRef.current).map((m) => ({ role: m.role, content: m.text }));
    if (!newTurns.length) return;
    lastSummarizedTurnRef.current = userTurns;
    const foldedCount = convo.length;
    fetch((window.QMS_CONFIG.API_BASE || '') + '/summarize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ history: newTurns, previous_summary: summaryRef.current }),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.summary === 'string') {
          summaryRef.current = d.summary;
          summarizedCountRef.current = foldedCount;
        }
      })
      .catch(() => {});
  }, [messages, busy, cfg]);

  // Persist the current thread after each completed turn (not mid-stream). Saves
  // the messages, the source docs they reference, and the rolling summary, then
  // refreshes the sidebar list. The `!busy` guard means this fires once per turn,
  // when streaming settles, rather than on every token.
  React.useEffect(() => {
    if (busy || !History || !convIdRef.current) return;
    // A thread was just opened for viewing — don't persist (would bump updated_at
    // to now and reorder it to today). Clear the flag; the next real change saves.
    if (skipNextSaveRef.current) { skipNextSaveRef.current = false; return; }
    const convo = messages.filter((m) => (m.role === 'user' || m.role === 'assistant') && (m.text || '').trim());
    if (!convo.length) return;
    const first = messages.find((m) => m.role === 'user');
    const title = ((first && first.text) || 'Untitled chat').slice(0, 80);
    // Only keep the docs this thread actually cites, not the whole cache.
    const refIds = new Set();
    messages.forEach((m) => (m.sources || []).forEach((sid) => refIds.add(sid)));
    const docs = {};
    refIds.forEach((sid) => { if (docsById[sid]) docs[sid] = docsById[sid]; });
    // Normalize away the transient streaming flag so a reload never shows a cursor.
    const clean = messages.map((m) => (m.streaming ? { ...m, streaming: false } : m));
    History.save(convIdRef.current, {
      title, messages: clean, docsById: docs,
      summary: summaryRef.current, summarizedCount: summarizedCountRef.current,
    }).then(() => History.list()).then(setConversations);
  }, [messages, busy, docsById]);

  const isEmpty = messages.length === 0 && !busy;
  const firstUser = messages.find((m) => m.role === 'user');
  const headerTitle = isEmpty ? 'New question' : (firstUser ? firstUser.text : 'New question');
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant');
  const lastDocId = lastAssistant && lastAssistant.sources && lastAssistant.sources[0];

  function togglePanel() {
    if (openDoc) { setOpenDoc(null); return; }
    if (lastDocId && docsById[lastDocId]) setOpenDoc(docsById[lastDocId]);
  }

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', background: 'var(--surface-page)' }}>
      <Sidebar conversations={conversations} activeId={activeId} onSelect={(id) => { setView('chat'); openConversation(id); }} onDelete={deleteConversation} onNewChat={() => { setView('chat'); newChat(); }} view={view} onNavigate={setView} roles={ROLE_LIST} role={role} onRoleChange={setRole} />

      {view === 'rules' ? <RulesManager /> : view === 'compliance' ? <ComplianceChecker />
        : view === 'project' ? <ProjectStart role={role} roleLabel={roleObj && roleObj.label} /> : (
      /* Main column */
      <div style={{ position: 'relative', flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* Header */}
        <header style={{ height: 'var(--header-h)', flex: 'none', display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--gray-0)' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{headerTitle}</div>
          </div>
          {cfg && cfg.model && (
            <span title="Active answer model" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
              {cfg.model}
            </span>
          )}
          <Badge tone="success" dot>{KB_LABEL}</Badge>
          <IconButton label="Toggle source panel" active={!!openDoc} onClick={togglePanel}><PanelIcon /></IconButton>
        </header>

        {/* Scroll area */}
        <div ref={scrollRef} onScroll={onScroll} style={{ flex: 1, overflowY: 'auto' }}>
          {isEmpty
            ? <EmptyState suggestions={roleSuggestions} onPick={send} />
            : <ChatThread messages={messages} busy={busy} busyLabel={busyLabel} streamingId={streamingId} docs={docsById} onOpenSource={(id) => setOpenDoc(docsById[id])} />}
        </div>

        {/* Composer */}
        <div style={{ flex: 'none', padding: '12px 24px 18px', background: 'linear-gradient(to top, var(--surface-page) 70%, transparent)' }}>
          <div style={{ maxWidth: 'var(--content-max)', margin: '0 auto' }}>
            <ChatComposer value={input} onChange={(e) => setInput(e.target.value)} onSend={send} disabled={busy}
              hint="Answers cite retrieved documents. Verify against the controlled copy." />
          </div>
        </div>

        <SourceDrawer open={!!openDoc} document={openDoc} onClose={() => setOpenDoc(null)} />
      </div>
      )}
    </div>
  );
}

window.App = App;
