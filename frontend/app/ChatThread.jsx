// ChatThread — renders the message list with bubbles, source cards, typing state.
const { MessageBubble, SourceCard, TypingIndicator } = window.QMSDesignSystem;
const { CURRENT_USER } = window.QMS_CONFIG;   // placeholder identity (no login yet)

// Inline formatting within a line: **bold**.
function renderInline(text) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**')
      ? <strong key={i} style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{p.slice(2, -2)}</strong>
      : <span key={i}>{p}</span>
  );
}

// Render the LLM's Markdown answer (paragraphs, *unordered* / 1. ordered lists,
// **bold**) as proper blocks. The model emits real newlines, but a normal HTML
// block collapses them — so without this, lists flatten into one paragraph with
// stray "*". We group lines into blocks and render <ul>/<ol>/<p> accordingly.
function renderMarkdown(text) {
  const lines = String(text).replace(/\r/g, '').split('\n');
  const blocks = [];
  let para = [];
  let list = null; // { ordered, items: [] }
  const flushPara = () => { if (para.length) { blocks.push({ type: 'p', lines: para }); para = []; } };
  const flushList = () => { if (list) { blocks.push({ type: 'list', ordered: list.ordered, items: list.items }); list = null; } };

  lines.forEach((raw) => {
    const line = raw.trim();
    const ul = line.match(/^[*\-•]\s+(.*)$/);
    const ol = line.match(/^\d+[.)]\s+(.*)$/);
    if (ul) {
      flushPara();
      if (!list || list.ordered) { flushList(); list = { ordered: false, items: [] }; }
      list.items.push(ul[1]);
    } else if (ol) {
      flushPara();
      if (!list || !list.ordered) { flushList(); list = { ordered: true, items: [] }; }
      list.items.push(ol[1]);
    } else if (line === '') {
      flushPara(); flushList();
    } else {
      flushList();
      para.push(line);
    }
  });
  flushPara(); flushList();

  return blocks.map((b, i) => {
    if (b.type === 'list') {
      const Tag = b.ordered ? 'ol' : 'ul';
      return (
        <Tag key={i} style={{ margin: '6px 0', paddingLeft: 22, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}
        </Tag>
      );
    }
    return (
      <p key={i} style={{ margin: i === 0 ? '0 0 8px' : '8px 0' }}>
        {b.lines.map((ln, j) => (
          <React.Fragment key={j}>{renderInline(ln)}{j < b.lines.length - 1 ? <br /> : null}</React.Fragment>
        ))}
      </p>
    );
  });
}

const secs = (ms) => (ms == null ? '–' : (ms / 1000).toFixed(1) + 's');

// Collapsible process trace: which model ran, how it was retrieved, and timings.
function ProcessTrace({ meta }) {
  if (!meta) return null;
  const grounded = meta.grounded ? 'grounded' : 'general';
  const summary = [
    meta.model,
    meta.num_sources != null ? meta.num_sources + ' sources' : null,
    'total ' + secs(meta.total_ms),
  ].filter(Boolean).join(' · ');
  const rows = [
    ['Model', meta.model],
    ['Retrieval', meta.mode === 'chunked' ? 'chunked (late-chunking, dense + sparse RRF)' : meta.mode],
    ['Sources (top_k)', (meta.num_sources != null ? meta.num_sources : '–') + (meta.top_k ? ' / ' + meta.top_k : '')],
    ['Source IDs', (meta.source_ids || []).join(', ') || '–'],
    ['Top score', meta.top_score != null ? String(meta.top_score) : '–'],
    ['Answer mode', grounded + (meta.threshold != null ? ' (threshold ' + meta.threshold + ')' : '')],
    ['Context window', meta.num_ctx ? meta.num_ctx + ' tokens' : '–'],
    ['Retrieval time', secs(meta.retrieval_ms)],
    ['Generation time', secs(meta.generation_ms)],
  ];
  return (
    <details style={{ marginTop: 2 }}>
      <summary style={{ cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-faint)', listStyle: 'none' }}>
        ⚙ Process · {summary}
      </summary>
      <div style={{ marginTop: 8, padding: '10px 12px', background: 'var(--gray-50)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 14px' }}>
        {rows.map(([k, v]) => (
          <React.Fragment key={k}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{k}</div>
            <div style={{ fontSize: 11, color: 'var(--text-body)', fontFamily: 'var(--font-mono)', wordBreak: 'break-word' }}>{v}</div>
          </React.Fragment>
        ))}
      </div>
    </details>
  );
}

function ChatThread({ messages, busy, busyLabel, streamingId, docs, onOpenSource }) {
  return (
    <div style={{ width: '100%', maxWidth: 'var(--content-max)', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 22, padding: '28px 24px 12px' }}>
      {messages.map((m) => {
        if (m.role === 'user') {
          return <MessageBubble key={m.id} role="user" authorName={CURRENT_USER}>{m.text}</MessageBubble>;
        }
        const sources = (m.sources || []).map((id) => docs[id]).filter(Boolean);
        return (
          <MessageBubble key={m.id} role="assistant" timestamp={m.time}
            footer={(sources.length || m.meta) ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sources.length ? (
                  <React.Fragment>
                    <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: 'var(--ls-caps)', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 2 }}>
                      {sources.length} sources
                    </div>
                    {sources.map((d, i) => (
                      <SourceCard key={d.docId} {...d} defaultOpen={i === 0} onOpenPreview={() => onOpenSource(d.docId)} />
                    ))}
                  </React.Fragment>
                ) : null}
                <ProcessTrace meta={m.meta} />
              </div>
            ) : null}>
            {renderMarkdown(m.text)}
            {m.streaming ? <span className="qms-cursor">▍</span> : null}
          </MessageBubble>
        );
      })}
      {busy && !streamingId && (
        <div style={{ paddingLeft: 48 }}><TypingIndicator label={busyLabel} /></div>
      )}
    </div>
  );
}

window.ChatThread = ChatThread;
