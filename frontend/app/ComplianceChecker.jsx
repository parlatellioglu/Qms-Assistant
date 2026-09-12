// ComplianceChecker — run the authored rule set against an uploaded document and
// show the structured result (verdict, score, per-rule findings). Talks to
//   GET  /compliance/doc-kinds     (which document types have a rule set)
//   POST /compliance/check-upload  (upload → extract → check → report)
//   GET  /config                   (which model the AI content tier uses)
// This view is upload-only. The built-in corpus documents are checkable through
// POST /compliance/check with a doc_id — used by the tests and the CLI scripts.
// The deterministic tiers run instantly; the optional AI content tier is slower.
const { Badge } = window.QMSDesignSystem;
const { API_BASE } = window.QMS_CONFIG;

const VERDICT = {
  compliant: { label: 'Compliant', tone: 'success', color: 'var(--green-600, #16a34a)' },
  partially_compliant: { label: 'Partially compliant', tone: 'warning', color: 'var(--orange-500, #ea580c)' },
  non_compliant: { label: 'Non-compliant', tone: 'danger', color: 'var(--red-600, #dc2626)' },
};
const SEV_COLOR = {
  blocker: 'var(--red-500, #dc2626)', high: 'var(--orange-500, #ea580c)',
  medium: 'var(--blue-500, #3b82f6)', low: 'var(--text-faint, #9ca3af)',
};
// A finding's semantic bucket (sent by the backend) drives its colour, label and
// filtering. "missing" (eksik) is split out from "violations" (ihlal) so an
// absent required section reads differently from a present-but-wrong one.
const BUCKET_UI = {
  passed:     { icon: '✓', color: 'var(--green-600, #16a34a)', label: 'Passed' },
  violations: { icon: '✗', color: 'var(--red-600, #dc2626)', label: 'Violation' },
  missing:    { icon: '–', color: 'var(--amber-600, #d97706)', label: 'Missing' },
  skipped:    { icon: '•', color: 'var(--text-faint, #9ca3af)', label: 'Skipped' },
  errors:     { icon: '!', color: 'var(--purple-600, #7c3aed)', label: 'Error' },
};
// Display order: problems first, resolved/informational last.
const BUCKET_ORDER = ['violations', 'missing', 'errors', 'skipped', 'passed'];
// Fallback bucket for a finding the backend didn't tag (older/ad-hoc responses).
const bucketOf = (f) => f.bucket || (f.status === 'pass' ? 'passed'
  : f.status === 'skipped' ? 'skipped' : f.status === 'error' ? 'errors' : 'violations');

// Clickable stat tile: click to filter the findings to that bucket, click again
// (or the active tile) to clear. Disabled when the bucket is empty.
function StatButton({ label, value, color, active, dim, disabled, onClick }) {
  return (
    <button type="button" onClick={disabled ? undefined : onClick} disabled={disabled}
      title={disabled ? undefined : (active ? 'Clear filter' : `Show only "${label}"`)}
      style={{
        flex: '1 1 0', minWidth: 74, textAlign: 'center', padding: '8px 6px',
        background: active ? 'color-mix(in srgb, ' + (color || 'var(--text-muted)') + ' 12%, var(--gray-0))' : 'var(--gray-0)',
        border: '1px solid ' + (active ? (color || 'var(--border-default)') : 'var(--border-subtle)'),
        boxShadow: active ? '0 0 0 1px ' + (color || 'transparent') + ' inset' : 'none',
        borderRadius: 'var(--radius-md)', cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.45 : (dim ? 0.5 : 1), transition: 'opacity .15s, background .15s',
      }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--text-strong)', lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{label}</div>
    </button>
  );
}

function ScoreBar({ score }) {
  const pct = Math.round((score || 0) * 100);
  const color = pct >= 80 ? 'var(--green-500, #22c55e)' : pct >= 50 ? 'var(--orange-500, #ea580c)' : 'var(--red-500, #dc2626)';
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4 }}>
        <span>Compliance score</span><span style={{ fontWeight: 600, color: 'var(--text-strong)' }}>{pct}%</span>
      </div>
      <div style={{ height: 8, borderRadius: 999, background: 'var(--gray-100)', overflow: 'hidden' }}>
        <div style={{ width: pct + '%', height: '100%', background: color, borderRadius: 999, transition: 'width .4s ease' }} />
      </div>
    </div>
  );
}

function FindingRow({ f }) {
  const s = BUCKET_UI[bucketOf(f)] || BUCKET_UI.errors;
  return (
    <div style={{ display: 'flex', gap: 11, padding: '11px 14px', marginBottom: 6, background: 'var(--gray-0)', border: '1px solid var(--border-subtle)', borderLeft: `3px solid ${s.color}`, borderRadius: 'var(--radius-md)' }}>
      <span title={s.label} style={{ flex: 'none', width: 20, height: 20, marginTop: 1, borderRadius: '50%', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: '#fff', background: s.color }}>{s.icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0, fontSize: 13.5, color: 'var(--text-strong)', fontWeight: 500 }}>{f.statement || f.rule_id}</div>
          <span style={{ flex: 'none', fontSize: 11, fontWeight: 700, color: s.color, background: 'color-mix(in srgb, ' + s.color + ' 13%, transparent)', padding: '2px 9px', borderRadius: 'var(--radius-pill, 999px)' }}>{s.label}</span>
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--text-body)', marginTop: 3 }}>{f.detail}</div>
        {f.fix_hint && (
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 5, padding: '6px 9px', background: 'var(--gray-50)', borderRadius: 'var(--radius-sm)' }}>
            ↳ <strong style={{ color: 'var(--text-body)' }}>Fix:</strong> {f.fix_hint}
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, fontSize: 11 }}>
          <span title={f.severity} style={{ width: 8, height: 8, borderRadius: '50%', background: SEV_COLOR[f.severity] || 'var(--text-faint)' }} />
          <span style={{ color: 'var(--text-muted)' }}>{f.severity}</span>
          <span style={{ color: 'var(--text-faint)' }}>·</span>
          <span style={{ color: 'var(--text-muted)' }}>{f.tier}</span>
          <span style={{ color: 'var(--text-faint)' }}>·</span>
          <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-faint)' }}>{f.rule_id}</span>
        </div>
      </div>
    </div>
  );
}

const SUPPORTED_UPLOAD = '.docx,.xlsx,.pptx,.txt,.md';

function ComplianceChecker() {
  const [contentTier, setContentTier] = React.useState(false);
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [report, setReport] = React.useState(null);
  const [filter, setFilter] = React.useState(null); // active bucket filter, or null = all
  const [cfg, setCfg] = React.useState(null); // backend runtime config (which models)
  const [docKinds, setDocKinds] = React.useState([]); // rule-set targets for an upload
  const [uploadFile, setUploadFile] = React.useState(null);
  const [uploadKind, setUploadKind] = React.useState('');
  const fileInputRef = React.useRef(null);

  // Pull runtime config so we can show which model the AI content tier uses,
  // mirroring how the assistant shows its answer model in its header.
  React.useEffect(() => {
    fetch(`${API_BASE}/config`)
      .then((r) => r.ok ? r.json() : null)
      .then((c) => c && setCfg(c))
      .catch(() => {});
  }, []);

  // Which doc_kinds have a rule set — the target the uploaded file is checked against.
  React.useEffect(() => {
    fetch(`${API_BASE}/compliance/doc-kinds`)
      .then((r) => r.ok ? r.json() : null)
      .then((d) => {
        const kinds = (d && d.doc_kinds) || [];
        setDocKinds(kinds);
        setUploadKind((cur) => cur || kinds[0] || '');
      })
      .catch(() => {});
  }, []);

  const canRun = !!uploadFile && !!uploadKind;

  async function run() {
    if (!canRun) return;
    setRunning(true); setError(null); setReport(null); setFilter(null);
    try {
      const form = new FormData();
      form.append('file', uploadFile);
      form.append('doc_kind', uploadKind);
      form.append('content_tier', contentTier ? 'true' : 'false');
      const res = await fetch(`${API_BASE}/compliance/check-upload`, { method: 'POST', body: form });
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail || `HTTP ${res.status}`); }
      setReport(await res.json());
    } catch (e) { setError(String(e.message || e)); }
    finally { setRunning(false); }
  }

  const verdict = report && (VERDICT[report.verdict] || { label: report.verdict, tone: 'neutral', color: 'var(--text-muted)' });

  // Disjoint per-bucket counts derived from the findings (missing split out from
  // violations), so the tiles + filter + list stay consistent with each other.
  const allFindings = report ? report.findings : [];
  const groupCounts = allFindings.reduce((a, f) => { const b = bucketOf(f); a[b] = (a[b] || 0) + 1; return a; }, {});
  const shownFindings = (filter ? allFindings.filter((f) => bucketOf(f) === filter) : allFindings)
    .slice().sort((a, b) => BUCKET_ORDER.indexOf(bucketOf(a)) - BUCKET_ORDER.indexOf(bucketOf(b)));
  const toggleFilter = (b) => setFilter((cur) => (cur === b ? null : b));
  const renderTile = (b) => {
    const ui = BUCKET_UI[b]; const n = groupCounts[b] || 0;
    return (
      <StatButton key={b} label={ui.label} value={n} color={n ? ui.color : undefined}
        active={filter === b} dim={!!filter && filter !== b} disabled={!n}
        onClick={() => toggleFilter(b)} />
    );
  };

  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--surface-page)' }}>
      <header style={{ height: 'var(--header-h)', flex: 'none', display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px', borderBottom: '1px solid var(--border-subtle)', background: 'var(--gray-0)' }}>
        <div style={{ flex: 1, fontSize: 15, fontWeight: 600, color: 'var(--text-strong)' }}>Compliance Check</div>
        {cfg && cfg.compliance_model && (
          <span title="AI content-analysis model" style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            {cfg.compliance_model}
          </span>
        )}
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Check a document against the rules</span>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '18px 24px' }}>
        <div style={{ maxWidth: 'var(--content-max, 860px)', margin: '0 auto' }}>

          {/* Controls — upload a document, check it, then it is discarded. */}
          <div style={{ background: 'var(--gray-0)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg, 12px)', padding: 18, marginBottom: 18 }}>

            <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-strong)', marginBottom: 6 }}>File</div>
            <div
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
              onDragOver={(e) => { e.preventDefault(); }}
              onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files && e.dataTransfer.files[0];
                if (f) { setUploadFile(f); setReport(null); setError(null); }
              }}
              style={{ padding: '18px 16px', textAlign: 'center', cursor: 'pointer', border: '1.5px dashed var(--border-default)', borderRadius: 'var(--radius-md)', background: 'var(--surface-page)' }}>
              {uploadFile ? (
                <div style={{ fontSize: 13, color: 'var(--text-strong)' }}>
                  📄 <strong>{uploadFile.name}</strong>
                  <span style={{ color: 'var(--text-faint)', marginLeft: 8 }}>{Math.max(1, Math.round(uploadFile.size / 1024))} KB</span>
                  <div style={{ fontSize: 11.5, color: 'var(--blue-600, #2563eb)', marginTop: 4 }}>Click or drag to replace</div>
                </div>
              ) : (
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Drag a file here, or <span style={{ color: 'var(--blue-600, #2563eb)', fontWeight: 600 }}>click to choose one</span>
                  <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 4 }}>Word, Excel, PowerPoint, text (.docx .xlsx .pptx .txt .md)</div>
                </div>
              )}
            </div>
            <input ref={fileInputRef} type="file" accept={SUPPORTED_UPLOAD} style={{ display: 'none' }}
              onChange={(e) => { const f = e.target.files && e.target.files[0]; if (f) { setUploadFile(f); setReport(null); setError(null); } }} />

            <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--text-strong)', margin: '14px 0 6px' }}>Document type (which rule set to check against)</div>
            <select
              value={uploadKind} disabled={!docKinds.length}
              onChange={(e) => { setUploadKind(e.target.value); setReport(null); }}
              style={{ width: '100%', padding: '9px 10px', fontSize: 13, fontFamily: 'var(--font-sans)', color: 'var(--text-body)', background: 'var(--surface-page)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
              {!docKinds.length && <option value="">No rule set defined</option>}
              {docKinds.map((k) => <option key={k} value={k}>{k}</option>)}
            </select>
            <div style={{ fontSize: 11.5, color: 'var(--text-faint)', marginTop: 6 }}>
              The uploaded file is only checked — it is deleted afterwards, never stored or indexed.
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--text-body)', cursor: 'pointer', marginTop: 14 }}>
              <input type="checkbox" checked={contentTier} onChange={(e) => setContentTier(e.target.checked)} />
              Also run the AI content analysis
              <span style={{ fontSize: 11.5, color: 'var(--text-faint)' }}>
                (evaluates the content rules; slower{cfg && cfg.compliance_model ? ' · ' : ''}
                {cfg && cfg.compliance_model && (
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{cfg.compliance_model}</span>
                )})
              </span>
            </label>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 16 }}>
              <button onClick={run} disabled={running || !canRun}
                style={{ padding: '9px 20px', fontSize: 13, fontWeight: 600, borderRadius: 'var(--radius-md)', border: 'none', background: 'var(--blue-600, #2563eb)', color: '#fff', cursor: running ? 'default' : 'pointer', opacity: (running || !canRun) ? 0.55 : 1 }}>
                {running ? 'Checking…' : 'Check'}
              </button>
              {running && contentTier && (
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>AI content analysis is running, this can take a while…</span>
              )}
            </div>
          </div>

          {error && <div style={{ color: 'var(--red-600, #dc2626)', fontSize: 13, marginBottom: 14 }}>⚠ {error}</div>}

          {/* Report */}
          {report && (
            <React.Fragment>
              <div style={{ background: 'var(--gray-0)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg, 12px)', padding: 18, marginBottom: 18 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '5px 12px', borderRadius: 'var(--radius-pill, 999px)', fontSize: 13, fontWeight: 600, color: '#fff', background: verdict.color }}>
                    {verdict.label}
                  </span>
                  <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                    {report.document.title} · <span style={{ fontFamily: 'var(--font-mono)' }}>{report.document.id}</span>
                  </span>
                  <span style={{ marginLeft: 'auto', fontSize: 11.5, color: 'var(--text-faint)' }}>
                    {report.content_tier
                      ? `including AI content analysis${cfg && cfg.compliance_model ? ' (' + cfg.compliance_model + ')' : ''}`
                      : 'automatic checks only'} · {report.elapsed_ms} ms
                  </span>
                </div>

                <ScoreBar score={report.score} />

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
                  {['passed', 'violations', 'missing', 'skipped'].map(renderTile)}
                  {(groupCounts.errors > 0) && renderTile('errors')}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 10 }}>
                  Click a tile to show only that group.
                  {!report.content_tier && (groupCounts.skipped > 0) && (
                    <span> “Skipped” means content rules that were not evaluated because the AI content analysis was off — tick the box above and run the check again to include them.</span>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 10 }}>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-faint)' }}>
                  Rule findings · {shownFindings.length}{filter ? ` / ${allFindings.length}` : ''}
                </div>
                {filter && (
                  <button type="button" onClick={() => setFilter(null)}
                    style={{ fontSize: 12, color: 'var(--blue-600, #2563eb)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
                    “{BUCKET_UI[filter].label}" filter · show all ✕
                  </button>
                )}
              </div>
              {shownFindings.map((f) => <FindingRow key={f.rule_id} f={f} />)}
              {!shownFindings.length && (
                <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '16px 0' }}>
                  {allFindings.length ? 'No findings in this group.' : 'No rules applied to this document.'}
                </div>
              )}
            </React.Fragment>
          )}

          {!report && !error && (
            <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '8px 0' }}>
              Upload a file, choose its document type, then click <strong>Check</strong>. The results show each
              rule's pass/violation/missing status, the reason, and the suggested fix.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

window.ComplianceChecker = ComplianceChecker;
