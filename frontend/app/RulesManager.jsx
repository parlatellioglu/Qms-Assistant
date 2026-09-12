// RulesManager — author/edit Compliance Checker rules from the UI, in plain
// language for non-technical quality staff. No JSON / regex / rule-ids exposed:
// you pick WHAT to check in friendly terms and fill simple fields; the app maps
// that to the underlying rule schema and the backend auto-assigns the id.
// Rules are organised BY DOCUMENT TYPE (doc_kind), each type its own rule set.
const { API_BASE } = window.QMS_CONFIG;

const SEV_COLOR = {
  blocker: 'var(--red-500, #dc2626)', high: 'var(--orange-500, #ea580c)',
  medium: 'var(--blue-500, #3b82f6)', low: 'var(--text-faint, #9ca3af)',
};
const SEV_LABEL = {
  blocker: 'Blocker — the document is treated as invalid', high: 'High', medium: 'Medium', low: 'Low',
};
const VERSION_BASELINE = '^[1-9]\\d*\\.\\d+$';

// Friendly check kinds. `key` maps to (or virtualises) a backend check.type.
const CHECK_KINDS = [
  { key: 'section_present', group: 'auto', label: 'The document must contain a specific section',
    help: 'Looks for a heading/section that must be present.' },
  { key: 'revision_history', group: 'auto', label: 'The document must contain a revision history',
    help: 'Looks for a revision history table with version rows.' },
  { key: 'signature_block', group: 'auto', label: 'The document must contain a signature/approval block',
    help: 'Looks for sign-off roles such as Prepared/Recommended/Approved.' },
  { key: 'version_baseline', group: 'auto', label: 'The version must be approved (1.0 or higher)',
    help: 'Checks the version is approved rather than a draft (0.x).' },
  { key: 'refs_resolve', group: 'auto', label: 'Referenced documents must exist in the system',
    help: 'Verifies that document ids cited in the text resolve.' },
  { key: 'id_trace', group: 'auto', label: 'Items must be traceable to another document',
    help: 'Checks that requirement/item ids link to another document.' },
  { key: 'llm_judge', group: 'ai', label: 'AI content check (your own question)',
    help: 'The AI judges the document against your plain-text question and gives a reason and a quote.' },
];
const KIND_LABEL = CHECK_KINDS.reduce((a, k) => (a[k.key] = k.label, a), {});

const splitList = (s) => String(s || '').split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
const joinList = (a) => (Array.isArray(a) ? a : []).join(', ');
const pretty = (o) => JSON.stringify(o, null, 2);

// --- map between the friendly form and the stored `check` object -------------
function friendlyToCheck(f) {
  if (f.useAdvanced) return JSON.parse(f.advancedJson);
  switch (f.kind) {
    case 'section_present': return { type: 'section_present', any_of: splitList(f.sections) };
    case 'revision_history': return { type: 'revision_history', min_versions: Math.max(1, parseInt(f.minVersions, 10) || 1) };
    case 'signature_block': return { type: 'signature_block', roles: splitList(f.roles) };
    case 'version_baseline': return { type: 'metadata_regex', field: 'version', pattern: VERSION_BASELINE };
    case 'refs_resolve': return { type: 'refs_resolve', id_pattern: 'CMMI-IT-\\d{3}(?!\\d)', ...(f.refsPublishedOnly ? { require_status: 'published' } : {}) };
    case 'id_trace': return { type: 'id_trace', from_pattern: `${(f.tracePrefix || 'FR').trim()}-\\d+`, to_doc_kind: (f.traceTarget || '').toUpperCase() };
    case 'llm_judge': {
      const mc = splitList(f.aiMustCover);
      return { type: 'llm_judge', criterion: f.aiQuestion.trim(), require_citation: !!f.aiRequireCitation, ...(mc.length ? { must_cover: mc } : {}) };
    }
    default: return { type: f.kind };
  }
}

function checkToFriendly(check) {
  const t = check && check.type;
  switch (t) {
    case 'section_present': return { kind: 'section_present', sections: joinList(check.any_of) };
    case 'revision_history': return { kind: 'revision_history', minVersions: check.min_versions || 3 };
    case 'signature_block': return { kind: 'signature_block', roles: joinList(check.roles) };
    case 'metadata_regex':
      if (check.field === 'version' && check.pattern === VERSION_BASELINE) return { kind: 'version_baseline' };
      return { kind: 'advanced', useAdvanced: true, advancedJson: pretty(check) };
    case 'refs_resolve': return { kind: 'refs_resolve', refsPublishedOnly: check.require_status === 'published' };
    case 'id_trace': return { kind: 'id_trace', tracePrefix: String(check.from_pattern || 'FR').split('-')[0], traceTarget: check.to_doc_kind || '' };
    case 'llm_judge': return { kind: 'llm_judge', aiQuestion: check.criterion || '', aiMustCover: joinList(check.must_cover), aiRequireCitation: check.require_citation !== false };
    default: return { kind: 'advanced', useAdvanced: true, advancedJson: pretty(check || {}) };
  }
}

function suggestStatement(f) {
  switch (f.kind) {
    case 'section_present': return `The document must contain this section: ${splitList(f.sections)[0] || '…'}.`;
    case 'revision_history': return `The document must contain a revision history with at least ${f.minVersions} version(s).`;
    case 'signature_block': return 'The document must contain a signature/approval block.';
    case 'version_baseline': return 'The document version must be approved (1.0 or higher).';
    case 'refs_resolve': return 'Documents cited in the text must exist in the system.';
    case 'id_trace': return `Items in the document must be traceable to the ${f.traceTarget || 'related'} document.`;
    case 'llm_judge': return f.aiQuestion || '';
    default: return '';
  }
}

function blankRule(docKind) {
  return {
    doc_kind: docKind || 'SRS', kind: 'section_present', severity: 'medium', statement: '',
    source: '', fix_hint: '', sections: '', minVersions: 3,
    roles: 'Prepared By, Recommended By, Approved By', refsPublishedOnly: true,
    tracePrefix: 'FR', traceTarget: 'BUR', aiQuestion: '', aiMustCover: '', aiRequireCitation: true,
    useAdvanced: false, advancedJson: pretty({ type: 'section_present', any_of: ['…'] }),
  };
}

function toForm(rule) {
  const base = blankRule((rule.applies_to && rule.applies_to.doc_kind) || 'SRS');
  const friendly = checkToFriendly(rule.check || {});
  return {
    ...base, ...friendly, _editingId: rule.id,
    doc_kind: (rule.applies_to && rule.applies_to.doc_kind) || 'SRS',
    severity: rule.severity || 'medium', statement: rule.statement || '',
    source: rule.source || '', fix_hint: rule.fix_hint || '',
  };
}

// --- small building blocks ---------------------------------------------------
const inputStyle = {
  width: '100%', padding: '8px 10px', fontSize: 13, fontFamily: 'var(--font-sans)',
  color: 'var(--text-body)', background: 'var(--gray-0)',
  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
};
function Field({ label, hint, children }) {
  return (
    <label style={{ display: 'block', marginBottom: 14 }}>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-strong)', marginBottom: 4 }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4 }}>{hint}</div>}
    </label>
  );
}
function Check({ checked, onChange, children }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-body)', cursor: 'pointer', marginBottom: 14 }}>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {children}
    </label>
  );
}

function RuleEditor({ meta, kinds, initial, onSave, onCancel, saving, error }) {
  const [f, setF] = React.useState(initial);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const isAI = f.kind === 'llm_judge';

  function pickKind(kind) {
    setF((p) => {
      const next = { ...p, kind, useAdvanced: false };
      if (!p.statement || p.statement === suggestStatement(p)) next.statement = suggestStatement(next);
      return next;
    });
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ width: 'min(600px, 94vw)', maxHeight: '92vh', overflowY: 'auto', background: 'var(--surface-page)', borderRadius: 'var(--radius-lg, 12px)', border: '1px solid var(--border-subtle)', padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.25)' }}>
        <div style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-strong)', marginBottom: 4 }}>
          {initial._editingId ? 'Edit rule' : 'New rule'}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 18 }}>
          {initial._editingId ? initial._editingId : `A new rule for ${f.doc_kind} documents`}
        </div>

        <Field label="Which document type?" hint="This rule applies only to documents of this type.">
          <select style={inputStyle} value={f.doc_kind} onChange={(e) => set('doc_kind', e.target.value)}>
            {Array.from(new Set([f.doc_kind, ...(kinds || [])])).filter(Boolean).map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </Field>

        <Field label="Ne kontrol edilmeli?" hint={(CHECK_KINDS.find((c) => c.key === f.kind) || {}).help}>
          <select style={inputStyle} value={f.useAdvanced ? '__adv' : f.kind}
            onChange={(e) => (e.target.value === '__adv' ? set('useAdvanced', true) : pickKind(e.target.value))}>
            <optgroup label="Otomatik kontroller">
              {CHECK_KINDS.filter((c) => c.group === 'auto').map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </optgroup>
            <optgroup label="Yapay zeka">
              {CHECK_KINDS.filter((c) => c.group === 'ai').map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </optgroup>
            <optgroup label="Uzman">
              <option value="__adv">Advanced (raw JSON)</option>
            </optgroup>
          </select>
        </Field>

        {/* Per-kind simple fields */}
        {!f.useAdvanced && f.kind === 'section_present' && (
          <Field label="Section heading" hint="Separate alternative spellings with commas (e.g. English + Turkish). At least one must be present.">
            <input style={inputStyle} value={f.sections} onChange={(e) => set('sections', e.target.value)} placeholder="Security Requirements, Güvenlik Gereksinimleri" />
          </Field>
        )}
        {!f.useAdvanced && f.kind === 'revision_history' && (
          <Field label="Minimum number of version rows?" hint="The smallest acceptable number of versions in the revision history.">
            <input type="number" min="1" style={inputStyle} value={f.minVersions} onChange={(e) => set('minVersions', e.target.value)} />
          </Field>
        )}
        {!f.useAdvanced && f.kind === 'signature_block' && (
          <Field label="Required sign-off roles" hint="Comma-separated. All of them must appear in the document.">
            <input style={inputStyle} value={f.roles} onChange={(e) => set('roles', e.target.value)} />
          </Field>
        )}
        {!f.useAdvanced && f.kind === 'version_baseline' && (
          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', background: 'var(--gray-50)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '10px 12px', marginBottom: 14 }}>
            No extra settings. Checks that the document version is 1.0 or higher (approved, not a draft).
          </div>
        )}
        {!f.useAdvanced && f.kind === 'refs_resolve' && (
          <Check checked={f.refsPublishedOnly} onChange={(v) => set('refsPublishedOnly', v)}>
            Only count references to "published" documents as valid
          </Check>
        )}
        {!f.useAdvanced && f.kind === 'id_trace' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Field label="Item prefix" hint="e.g. FR (FR-01, FR-02…)."><input style={inputStyle} value={f.tracePrefix} onChange={(e) => set('tracePrefix', e.target.value)} placeholder="FR" /></Field>
            <Field label="Hangi belgeye izlenmeli?">
              <select style={inputStyle} value={f.traceTarget} onChange={(e) => set('traceTarget', e.target.value)}>
                {Array.from(new Set([f.traceTarget, ...(kinds || [])])).filter(Boolean).map((k) => <option key={k} value={k}>{k}</option>)}
              </select>
            </Field>
          </div>
        )}
        {!f.useAdvanced && isAI && (
          <React.Fragment>
            <Field label="Check question for the AI" hint="Describe what to look for in your own words.">
              <textarea style={{ ...inputStyle, minHeight: 64, resize: 'vertical' }} value={f.aiQuestion} onChange={(e) => set('aiQuestion', e.target.value)} placeholder="Do the performance requirements include numeric targets (TPS, response time)?" />
            </Field>
            <Field label="The document must cover (optional)" hint="Comma-separated; each one must be addressed.">
              <input style={inputStyle} value={f.aiMustCover} onChange={(e) => set('aiMustCover', e.target.value)} placeholder="authentication, encryption, audit log" />
            </Field>
            <Check checked={f.aiRequireCitation} onChange={(v) => set('aiRequireCitation', v)}>Require the AI to justify its verdict with a quote from the document</Check>
          </React.Fragment>
        )}
        {f.useAdvanced && (
          <Field label="Check definition (JSON) — expert" hint="For technical users only. The other fields are ignored.">
            <textarea style={{ ...inputStyle, minHeight: 120, fontFamily: 'var(--font-mono)', fontSize: 12.5 }} value={f.advancedJson} onChange={(e) => set('advancedJson', e.target.value)} />
          </Field>
        )}

        <Field label="Summarise the rule in your own words" hint="This text is shown in the compliance report and to your team.">
          <textarea style={{ ...inputStyle, minHeight: 56, resize: 'vertical' }} value={f.statement} onChange={(e) => set('statement', e.target.value)} />
        </Field>

        <Field label="Severity" hint="If a \u201cBlocker\u201d rule fails, the whole document counts as non-compliant.">
          <select style={inputStyle} value={f.severity} onChange={(e) => set('severity', e.target.value)}>
            {(meta.severities || ['blocker', 'high', 'medium', 'low']).map((s) => <option key={s} value={s}>{SEV_LABEL[s] || s}</option>)}
          </select>
        </Field>

        <details style={{ marginBottom: 8 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12.5, color: 'var(--text-muted)' }}>Optional: source policy and suggested fix</summary>
          <div style={{ marginTop: 10 }}>
            <Field label="Source policy (optional)"><input style={inputStyle} value={f.source} onChange={(e) => set('source', e.target.value)} placeholder="e.g. CMMI RD / corporate template" /></Field>
            <Field label="Suggested fix (optional)" hint="Shown to the user when the rule fails.">
              <textarea style={{ ...inputStyle, minHeight: 44, resize: 'vertical' }} value={f.fix_hint} onChange={(e) => set('fix_hint', e.target.value)} />
            </Field>
          </div>
        </details>

        {error && <div style={{ color: 'var(--red-600, #dc2626)', fontSize: 12.5, margin: '6px 0' }}>⚠ {error}</div>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
          <button onClick={onCancel} disabled={saving} style={{ padding: '9px 18px', fontSize: 13, borderRadius: 'var(--radius-md)', border: '1px solid var(--border-default)', background: 'var(--gray-0)', color: 'var(--text-body)', cursor: 'pointer' }}>Cancel</button>
          <button onClick={() => onSave(f)} disabled={saving} style={{ padding: '9px 18px', fontSize: 13, fontWeight: 600, borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--blue-600, #2563eb)', color: '#fff', cursor: 'pointer', opacity: saving ? 0.6 : 1 }}>{saving ? 'Kaydediliyor…' : 'Kaydet'}</button>
        </div>
      </div>
    </div>
  );
}

function RulesManager() {
  const [rules, setRules] = React.useState([]);
  const [meta, setMeta] = React.useState({});
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [editing, setEditing] = React.useState(null);
  const [saving, setSaving] = React.useState(false);
  const [formError, setFormError] = React.useState(null);
  const [selectedKind, setSelectedKind] = React.useState(null);
  const [localKinds, setLocalKinds] = React.useState([]);

  async function load() {
    setLoading(true); setError(null);
    try {
      const res = await fetch(`${API_BASE}/rules`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRules(data.rules || []);
      setMeta(data.meta || {});
      setSelectedKind((cur) => {
        if (cur) return cur;
        const withRules = (data.rules || []).map((r) => r.applies_to && r.applies_to.doc_kind).filter(Boolean);
        return withRules[0] || (data.meta && data.meta.doc_kinds && data.meta.doc_kinds[0]) || null;
      });
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }
  React.useEffect(() => { load(); }, []);

  async function save(form) {
    let check;
    try { check = friendlyToCheck(form); }
    catch (e) { setFormError('The advanced JSON is not valid.'); return; }
    if (!form.statement.trim()) { setFormError('Please summarise the rule in your own words.'); return; }

    const rule = {
      applies_to: { doc_kind: form.doc_kind.trim().toUpperCase() },
      tier: (meta.check_types || {})[check.type],
      severity: form.severity,
      statement: form.statement.trim(),
      check,
      source: form.source.trim(),
      fix_hint: form.fix_hint.trim(),
    };
    if (editing._editingId) rule.id = editing._editingId;   // keep id on edit; new = auto-assigned

    setSaving(true); setFormError(null);
    try {
      const isEdit = !!editing._editingId;
      const url = isEdit ? `${API_BASE}/rules/${encodeURIComponent(editing._editingId)}` : `${API_BASE}/rules`;
      const res = await fetch(url, { method: isEdit ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(rule) });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || `HTTP ${res.status}`); }
      setSelectedKind(rule.applies_to.doc_kind);
      setEditing(null);
      await load();
    } catch (e) { setFormError(String(e.message || e)); }
    finally { setSaving(false); }
  }

  async function remove(rule) {
    if (!window.confirm(`Delete rule '${rule.id}'?`)) return;
    try {
      const res = await fetch(`${API_BASE}/rules/${encodeURIComponent(rule.id)}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await load();
    } catch (e) { setError(String(e)); }
  }

  function addDocType() {
    const raw = window.prompt('New document type code (e.g. PMP, SAT_PLAN, BUR):');
    if (!raw) return;
    const kind = raw.trim().toUpperCase().replace(/\s+/g, '_');
    if (!kind) return;
    setLocalKinds((p) => (p.includes(kind) ? p : [...p, kind]));
    setSelectedKind(kind);
  }

  function startNew() { setFormError(null); setEditing({ ...blankRule(selectedKind) }); }
  function startEdit(rule) { setFormError(null); setEditing(toForm(rule)); }

  const countByKind = rules.reduce((acc, r) => {
    const k = r.applies_to && r.applies_to.doc_kind;
    if (k) acc[k] = (acc[k] || 0) + 1;
    return acc;
  }, {});
  const allKinds = Array.from(new Set([...(meta.doc_kinds || []), ...Object.keys(countByKind), ...localKinds])).sort();
  const shown = rules.filter((r) => r.applies_to && r.applies_to.doc_kind === selectedKind);

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--surface-page)' }}>
      <header style={{ height: 'var(--header-h)', flex: 'none', display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--gray-0)' }}>
        <div style={{ flex: 1, fontSize: 15, fontWeight: 600, color: 'var(--text-strong)' }}>Compliance Rules</div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{rules.length} rule(s) · {allKinds.length} document type(s)</span>
        <button onClick={startNew} disabled={!selectedKind} style={{ padding: '7px 14px', fontSize: 13, fontWeight: 600, borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--blue-600, #2563eb)', color: '#fff', cursor: selectedKind ? 'pointer' : 'not-allowed', opacity: selectedKind ? 1 : 0.5 }}>+ New rule</button>
      </header>

      <div style={{ flex: 'none', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', padding: '12px 24px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--gray-0)' }}>
        {allKinds.map((k) => {
          const active = k === selectedKind; const n = countByKind[k] || 0;
          return (
            <button key={k} onClick={() => setSelectedKind(k)} style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 11px', fontSize: 12.5,
              borderRadius: 'var(--radius-pill, 999px)', cursor: 'pointer',
              border: active ? '1px solid var(--blue-400, #60a5fa)' : '1px solid var(--border-subtle)',
              background: active ? 'var(--blue-50)' : 'var(--surface-page)',
              color: active ? 'var(--blue-700)' : 'var(--text-body)', fontWeight: active ? 600 : 400,
            }}>{k}<span style={{ fontSize: 11, color: active ? 'var(--blue-500)' : 'var(--text-faint)' }}>{n}</span></button>
          );
        })}
        <button onClick={addDocType} style={{ padding: '5px 11px', fontSize: 12.5, borderRadius: 'var(--radius-pill, 999px)', border: '1px dashed var(--border-default)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>+ Document type</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '18px 24px' }}>
        <div style={{ maxWidth: 'var(--content-max, 860px)', margin: '0 auto' }}>
          {loading && <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>}
          {error && <div style={{ color: 'var(--red-600, #dc2626)', fontSize: 13 }}>⚠ {error}</div>}
          {!loading && selectedKind && (
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 10 }}>{selectedKind} · {shown.length} kural</div>
          )}
          {shown.map((r) => (
            <div key={r.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '11px 14px', marginBottom: 6, background: 'var(--gray-0)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)' }}>
              <span title={SEV_LABEL[r.severity] || r.severity} style={{ marginTop: 5, flex: 'none', width: 9, height: 9, borderRadius: '50%', background: SEV_COLOR[r.severity] || 'var(--text-faint)' }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, color: 'var(--text-strong)', fontWeight: 500 }}>{r.statement}</div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 3 }}>
                  {KIND_LABEL[(r.check && r.check.type)] || (r.check && r.check.type)}{r.check && r.check.type === 'llm_judge' ? ' · yapay zeka' : ''}
                </div>
              </div>
              <button onClick={() => startEdit(r)} style={{ flex: 'none', padding: '5px 10px', fontSize: 12, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', background: 'var(--gray-0)', color: 'var(--text-body)', cursor: 'pointer' }}>Edit</button>
              <button onClick={() => remove(r)} style={{ flex: 'none', padding: '5px 10px', fontSize: 12, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', background: 'var(--gray-0)', color: 'var(--red-600, #dc2626)', cursor: 'pointer' }}>Sil</button>
            </div>
          ))}
          {!loading && selectedKind && !shown.length && !error && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '20px 0' }}>
              No rules yet for <strong>{selectedKind}</strong>. Click “+ New rule” to add the first one.
            </div>
          )}
        </div>
      </div>

      {editing && <RuleEditor meta={meta} kinds={allKinds} initial={editing} onSave={save} onCancel={() => setEditing(null)} saving={saving} error={formError} />}
    </div>
  );
}

window.RulesManager = RulesManager;
