// Sidebar — brand, new-chat, conversation history, user footer.
// Reads primitives from the design-system bundle (window namespace) at render time.
const { Button, IconButton, Avatar } = window.QMSDesignSystem;

// Placeholder identity (no login yet) — see CURRENT_USER in config.js. Avatar
// derives its initials from the first two words.
const { CURRENT_USER } = window.QMS_CONFIG;

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>
  );
}
function ChatIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
  );
}
function SearchIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
  );
}
function RulesIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></svg>
  );
}
function RouteIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="6" cy="19" r="3" /><circle cx="18" cy="5" r="3" /><path d="M9 19h5a4 4 0 0 0 0-8h-4a4 4 0 0 1 0-8h5" /></svg>
  );
}
function ShieldIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="m9 12 2 2 4-4" /></svg>
  );
}

// Product mark: a document approval check. Inline SVG so the brand needs no
// image asset and inherits the theme's primary colour.
function BrandMark() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ display: 'block', flex: 'none' }}>
      <rect x="2" y="2" width="20" height="20" rx="5.5" fill="var(--blue-500)" />
      <path d="M7.75 12.4l2.6 2.6 5.9-5.9" stroke="#fff" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18" /><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /></svg>
  );
}
function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
  );
}

function NavItem({ icon, label, active, onClick }) {
  return (
    <button type="button" onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 9, width: '100%', textAlign: 'left',
        padding: '8px 10px', marginBottom: 2, border: 'none', cursor: 'pointer', borderRadius: 'var(--radius-sm)',
        background: active ? 'var(--blue-50)' : 'transparent',
        color: active ? 'var(--blue-700)' : 'var(--text-body)',
        fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: active ? 600 : 400,
      }}
      onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--gray-100)'; }}
      onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}>
      <span style={{ color: active ? 'var(--blue-500)' : 'var(--text-faint)', flex: 'none', display: 'inline-flex' }}>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function Sidebar({ conversations, activeId, onSelect, onDelete, onNewChat, view = 'chat', onNavigate, roles = [], role, onRoleChange }) {
  // Title search: filter the thread list by title, case-insensitive and
  // Turkish-aware (İ/ı fold correctly with the 'tr' locale). Empty query shows
  // the normal grouped list; a non-empty query with no matches says so.
  const [query, setQuery] = React.useState('');
  const q = query.trim().toLocaleLowerCase('tr');
  const filtered = q
    ? conversations.filter((c) => (c.title || '').toLocaleLowerCase('tr').includes(q))
    : conversations;

  // Preserve recency order within each date bucket (list() is already sorted).
  // Must match the labels history.js _bucket() returns.
  const order = ['Today', 'Yesterday', 'This week', 'Older'];
  const groups = filtered.reduce((acc, c) => {
    (acc[c.when] = acc[c.when] || []).push(c);
    return acc;
  }, {});
  const groupEntries = order.filter((w) => groups[w]).map((w) => [w, groups[w]]);

  return (
    <aside style={{
      width: 'var(--sidebar-w)', flex: 'none', height: '100%', boxSizing: 'border-box',
      background: 'var(--gray-0)', borderRight: '1px solid var(--border-subtle)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Brand — inline mark + product name (no binary asset to ship) */}
      <div style={{ height: 'var(--header-h)', display: 'flex', alignItems: 'center', padding: '0 18px', borderBottom: '1px solid var(--border-subtle)' }}>
        <BrandMark />
        <span style={{ marginLeft: 10, fontSize: 14, fontWeight: 650, color: 'var(--text-strong)', letterSpacing: '-0.01em' }}>QMS Assistant</span>
      </div>

      {/* New chat */}
      <div style={{ padding: '14px 14px 6px' }}>
        <Button variant="primary" fullWidth iconLeft={<PlusIcon />} onClick={onNewChat}>New question</Button>
      </div>

      {/* Primary nav — switch between the assistant and the rules editor */}
      <div style={{ padding: '4px 10px 6px' }}>
        <NavItem icon={<ChatIcon />} label="Assistant" active={view === 'chat'} onClick={() => onNavigate && onNavigate('chat')} />
        <NavItem icon={<RouteIcon />} label="New Project" active={view === 'project'} onClick={() => onNavigate && onNavigate('project')} />
        <NavItem icon={<ShieldIcon />} label="Compliance Check" active={view === 'compliance'} onClick={() => onNavigate && onNavigate('compliance')} />
        <NavItem icon={<RulesIcon />} label="Compliance Rules" active={view === 'rules'} onClick={() => onNavigate && onNavigate('rules')} />
      </div>

      {/* Search — filters the conversation list by title */}
      <div style={{ padding: '6px 14px 10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 10px', background: 'var(--gray-50)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', color: 'var(--text-faint)' }}>
          <SearchIcon />
          <input type="text" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search chats"
            style={{
              flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent',
              fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--text-body)',
            }} />
          {query && (
            <button type="button" onClick={() => setQuery('')} title="Clear" aria-label="Clear search"
              style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 18, height: 18, padding: 0, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-faint)' }}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--text-muted)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-faint)'; }}>
              <CloseIcon />
            </button>
          )}
        </div>
      </div>

      {/* History */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 8px' }}>
        {groupEntries.length === 0 ? (
          <div style={{ padding: '10px 10px', fontSize: 12, color: 'var(--text-faint)', fontStyle: 'italic' }}>
            {q ? 'No results' : 'No chats yet'}
          </div>
        ) : groupEntries.map(([when, items]) => (
          <div key={when} style={{ marginBottom: 10 }}>
            <div style={{ padding: '8px 8px 4px', fontSize: 10.5, fontWeight: 600, letterSpacing: 'var(--ls-caps)', textTransform: 'uppercase', color: 'var(--text-faint)' }}>{when}</div>
            {items.map((c) => {
              const active = c.id === activeId;
              return (
                <div key={c.id} className="qms-conv-row"
                  style={{
                    position: 'relative', display: 'flex', alignItems: 'center', marginBottom: 1,
                    borderRadius: 'var(--radius-sm)', background: active ? 'var(--blue-50)' : 'transparent',
                  }}
                  onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = 'var(--gray-100)'; }}
                  onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = 'transparent'; }}>
                  <button type="button" onClick={() => onSelect(c.id)} title={c.title}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 9, flex: 1, minWidth: 0, textAlign: 'left',
                      padding: '8px 10px', paddingRight: onDelete ? 28 : 10, border: 'none', cursor: 'pointer',
                      background: 'transparent', borderRadius: 'var(--radius-sm)',
                      color: active ? 'var(--blue-700)' : 'var(--text-body)',
                      fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: active ? 600 : 400,
                    }}>
                    <span style={{ color: active ? 'var(--blue-500)' : 'var(--text-faint)', flex: 'none', display: 'inline-flex' }}><ChatIcon /></span>
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.title}</span>
                  </button>
                  {onDelete && (
                    <button type="button" className="qms-conv-del" title="Delete chat"
                      onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
                      style={{
                        position: 'absolute', right: 5, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        width: 22, height: 22, padding: 0, border: 'none', borderRadius: 'var(--radius-sm)',
                        background: 'transparent', cursor: 'pointer', color: 'var(--text-faint)',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--gray-200)'; e.currentTarget.style.color = 'var(--red-500)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-faint)'; }}>
                      <TrashIcon />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User footer — avatar + role selector (soft personalization) */}
      <div style={{ borderTop: '1px solid var(--border-subtle)', padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Avatar name={CURRENT_USER} size="sm" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)' }}>{CURRENT_USER}</div>
          {roles.length ? (
            <select
              value={role} onChange={(e) => onRoleChange && onRoleChange(e.target.value)}
              title="Your role — tailors the starter questions"
              style={{
                marginTop: 2, width: '100%', maxWidth: '100%', padding: '2px 4px', fontSize: 11,
                fontFamily: 'var(--font-sans)', color: 'var(--text-muted)', background: 'transparent',
                border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
              }}>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
            </select>
          ) : (
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Quality Engineering</div>
          )}
        </div>
      </div>
    </aside>
  );
}

window.Sidebar = Sidebar;
