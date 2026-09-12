// ProjectStart — "New Project": the project lifecycle as a ladder of phases, read
// from GET /process-map (extracted from the loaded documents by
// scripts/corpus/build_process_map.py, never hand-authored here).
//
// This is guidance, not a tracker: it answers "which document do I write next,
// and what has to be true before I can", so it needs no persistence.
//
// A phase the documents name but never describe renders as an explicit "no detail
// in the loaded documents" note rather than an empty card. An empty card reads as
// a bug; the note tells the truth and points at a gap in the corpus.
const { Badge } = window.QMSDesignSystem;
const { API_BASE, ROLE_MATCH } = window.QMS_CONFIG;

// Does this item's text name the selected role? Short aliases (PM, QA, TL) match
// on a word boundary so "PM" doesn't fire inside "PMP"; longer labels match as a
// substring, case-insensitively. Used to highlight the phase items that concern
// the viewer's role — a lens over the map, never a filter that hides the rest.
function mentionsRole(text, role) {
  if (!text || !role || role === 'genel') return false;
  const aliases = (ROLE_MATCH && ROLE_MATCH[role]) || [];
  return aliases.some((a) => {
    if (a.length <= 4) return new RegExp(`(^|[^\\wğşçöüıİ])${a}([^\\wğşçöüıİ]|$)`, 'i').test(text);
    return text.toLowerCase().includes(a.toLowerCase());
  });
}

// field -> how it is introduced in the phase card. Order is the reading order:
// what you need before starting, what you produce, what closes the phase.
const SECTIONS = [
  { key: 'entry_criteria', label: 'Before you start', valueKey: 'text' },
  { key: 'deliverables', label: 'Documents you will produce', valueKey: 'name' },
  { key: 'exit_criteria', label: 'Completion condition', valueKey: 'text' },
  { key: 'policies', label: 'Process rule', valueKey: 'text' },
];

function Cite({ source }) {
  if (!source) return null;
  const where = [source.doc, source.locator].filter(Boolean).join(' · ');
  return (
    <span title={source.quote || ''}
      style={{ marginLeft: 6, fontSize: 10.5, color: 'var(--text-faint)', whiteSpace: 'nowrap' }}>
      {where}
    </span>
  );
}

// How many of a phase's items concern the selected role — drives the phase's
// "N relevant to you" badge and whether it auto-expands.
function roleHitCount(phase, role) {
  if (role === 'genel') return 0;
  let n = 0;
  for (const s of SECTIONS) {
    for (const item of phase[s.key] || []) {
      if (mentionsRole(item[s.valueKey], role)) n += 1;
    }
  }
  if (phase.gate && mentionsRole(phase.gate.name, role)) n += 1;
  return n;
}

function PhaseRow({ phase, index, total, expanded, onToggle, role }) {
  const items = SECTIONS
    .map((s) => ({ ...s, values: phase[s.key] || [] }))
    .filter((s) => s.values.length);
  const detailed = items.length > 0 || !!phase.gate;
  const hits = roleHitCount(phase, role);

  return (
    <div style={{ display: 'flex', gap: 12 }}>
      {/* Rail: numbered node + connector down to the next phase */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 'none' }}>
        <div style={{
          width: 26, height: 26, borderRadius: '50%', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600,
          background: detailed ? 'var(--blue-50)' : 'var(--gray-100)',
          color: detailed ? 'var(--blue-700)' : 'var(--text-faint)',
          border: `1px solid ${detailed ? 'var(--blue-200, #bfdbfe)' : 'var(--border-subtle)'}`,
        }}>{index + 1}</div>
        {index < total - 1 && (
          <div style={{ width: 1, flex: 1, minHeight: 18, background: 'var(--border-default)' }} />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0, paddingBottom: 18 }}>
        <button type="button" onClick={detailed ? onToggle : undefined}
          style={{
            display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left',
            background: 'none', border: 'none', padding: 0,
            cursor: detailed ? 'pointer' : 'default', fontFamily: 'var(--font-sans)',
          }}>
          <span style={{
            fontSize: 14, fontWeight: 600,
            color: detailed ? 'var(--text-strong)' : 'var(--text-muted)',
          }}>{phase.name}</span>
          {phase.gate && <Badge tone="info">{phase.gate.name}</Badge>}
          {hits > 0 && (
            <span style={{
              fontSize: 10.5, fontWeight: 600, padding: '2px 7px', borderRadius: 999,
              background: 'var(--blue-50)', color: 'var(--blue-700)',
              border: '1px solid var(--blue-200, #bfdbfe)',
            }}>{hits} relevant to you</span>
          )}
          {detailed && (
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-faint)' }}>
              {expanded ? 'hide' : `${items.length} item(s)`}
            </span>
          )}
        </button>

        {!detailed && (
          <div style={{ marginTop: 4, fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
            The loaded documents name this phase but do not describe it.
          </div>
        )}

        {detailed && expanded && (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {items.map((section) => (
              <div key={section.key}>
                <div style={{
                  fontSize: 10.5, fontWeight: 600, letterSpacing: 'var(--ls-caps)',
                  textTransform: 'uppercase', color: 'var(--text-faint)', marginBottom: 3,
                }}>{section.label}</div>
                <ul style={{ margin: 0, paddingLeft: 16 }}>
                  {section.values.map((item, i) => {
                    const mine = mentionsRole(item[section.valueKey], role);
                    return (
                      <li key={i} style={{
                        fontSize: 12.5, marginBottom: 2, listStyle: mine ? 'none' : 'disc',
                        marginLeft: mine ? -16 : 0, padding: mine ? '2px 8px' : 0,
                        borderRadius: 'var(--radius-sm)',
                        background: mine ? 'var(--blue-50)' : 'transparent',
                        color: mine ? 'var(--blue-800, #1e40af)' : 'var(--text-body)',
                        fontWeight: mine ? 500 : 400,
                      }}>
                        {mine && <span style={{ marginRight: 6 }}>◆</span>}
                        {item[section.valueKey]}
                        <Cite source={item.source} />
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
            {phase.gate && (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                This phase ends with: <strong>{phase.gate.name}</strong>
                <Cite source={phase.gate.source} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const hasDetail = (p) => !!p.gate || SECTIONS.some((s) => (p[s.key] || []).length);

function ProjectStart({ role = 'genel', roleLabel }) {
  const [map, setMap] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [open, setOpen] = React.useState({});
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    fetch(`${API_BASE}/process-map`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setMap)
      .catch((e) => setError(e.message));
  }, []);

  const processes = (map && map.processes) || [];
  const current = processes[active] || null;
  const phases = (current && current.phases) || [];
  const undetailed = phases.filter((p) => !hasDetail(p)).length;
  const roleHits = phases.reduce((n, p) => n + roleHitCount(p, role), 0);

  // Open the phases relevant to the role (or the first detailed phase for 'genel'),
  // so what matters to the viewer is visible without hunting. Re-runs when the
  // role or the loaded process changes.
  React.useEffect(() => {
    if (!phases.length) return;
    if (role !== 'genel' && roleHits > 0) {
      setOpen(Object.fromEntries(
        phases.filter((p) => roleHitCount(p, role) > 0).map((p) => [p.name, true])));
    } else {
      const opener = phases.find(hasDetail);
      setOpen(opener ? { [opener.name]: true } : {});
    }
  }, [role, active, map]);

  return (
    <main style={{ flex: 1, overflowY: 'auto', padding: '28px 32px', background: 'var(--gray-25, #fafafa)' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text-strong)', margin: '0 0 4px' }}>
          New Project
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '0 0 16px' }}>
          The project lifecycle extracted from the loaded process documents. Every item
          is shown with its source.
        </p>

        {/* Role lens: what the phases say about the viewer's role, without hiding
            the rest. Silent for 'genel' and when the role appears nowhere. */}
        {role !== 'genel' && phases.length > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, margin: '0 0 20px', padding: '9px 13px',
            background: 'var(--blue-50)', border: '1px solid var(--blue-200, #bfdbfe)',
            borderRadius: 'var(--radius-md)', fontSize: 12.5, color: 'var(--blue-800, #1e40af)',
          }}>
            <span style={{ fontSize: 13 }}>◆</span>
            {roleHits > 0
              ? <span>{roleHits} item(s) relevant to <strong>{roleLabel}</strong> highlighted.</span>
              : <span><strong>{roleLabel}</strong> is not named as a role anywhere in these process documents.</span>}
          </div>
        )}

        {error && (
          <div style={{ fontSize: 13, color: 'var(--red-600, #dc2626)' }}>
            Could not read the process map: {error}
          </div>
        )}

        {map && !processes.length && (
          <div style={{
            padding: 16, borderRadius: 'var(--radius-md)', background: 'var(--gray-0)',
            border: '1px solid var(--border-subtle)', fontSize: 13, color: 'var(--text-muted)',
          }}>
            The loaded documents do not define a project lifecycle.
            {map.built === false && ' (The process map has not been built yet.)'}
          </div>
        )}

        {/* Several process documents describe several distinct processes; let the
            user pick which one they are following instead of blending them. */}
        {processes.length > 1 && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap' }}>
            {processes.map((p, i) => (
              <button key={p.document} type="button" onClick={() => { setActive(i); setOpen({}); }}
                style={{
                  padding: '5px 11px', fontSize: 12, cursor: 'pointer',
                  fontFamily: 'var(--font-sans)', borderRadius: 'var(--radius-sm)',
                  border: `1px solid ${i === active ? 'var(--blue-500)' : 'var(--border-default)'}`,
                  background: i === active ? 'var(--blue-50)' : 'var(--gray-0)',
                  color: i === active ? 'var(--blue-700)' : 'var(--text-body)',
                  fontWeight: i === active ? 600 : 400,
                }}>
                {p.document}
              </button>
            ))}
          </div>
        )}

        {phases.length > 0 && (
          <div style={{
            padding: '20px 20px 4px', borderRadius: 'var(--radius-md)',
            background: 'var(--gray-0)', border: '1px solid var(--border-subtle)',
          }}>
            {phases.map((phase, i) => (
              <PhaseRow key={phase.name} phase={phase} index={i} total={phases.length}
                role={role} expanded={!!open[phase.name]}
                onToggle={() => setOpen((o) => ({ ...o, [phase.name]: !o[phase.name] }))} />
            ))}
          </div>
        )}

        {/* Name the gap rather than letting quiet phases look like a broken view. */}
        {undetailed > 0 && (
          <p style={{ fontSize: 12, color: 'var(--text-faint)', marginTop: 14 }}>
            {undetailed} phase(s) are named in the loaded documents but not detailed.
            Adding process documentation for them would fill the gap.
          </p>
        )}

        {current && (
          <p style={{ fontSize: 11, color: 'var(--text-faint)', marginTop: 8 }}>
            Source: {current.document}
          </p>
        )}
      </div>
    </main>
  );
}

window.ProjectStart = ProjectStart;
