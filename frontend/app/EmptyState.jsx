// EmptyState — welcome screen shown for a fresh conversation.
const { Badge: ES_Badge } = window.QMSDesignSystem;

function EmptyState({ suggestions, onPick }) {
  return (
    <div style={{
      height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '24px', textAlign: 'center',
    }}>
      <div style={{ maxWidth: 560 }}>
        <div style={{
          width: 52, height: 52, margin: '0 auto 18px', borderRadius: 'var(--radius-lg)',
          background: 'var(--blue-500)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: 'var(--shadow-md)',
        }}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="8" width="18" height="12" rx="3" /><path d="M12 8V4" /><circle cx="12" cy="3" r="1" /><path d="M8 13v2M16 13v2" />
          </svg>
        </div>
        <h1 style={{ margin: '0 0 8px', font: 'var(--text-h2)', color: 'var(--text-strong)' }}>Ask the Quality Management System</h1>
        <p style={{ margin: '0 0 28px', font: 'var(--text-body-lg)', color: 'var(--text-muted)' }}>
          Get answers grounded in your controlled procedures, policies, and test plans — every answer cites its sources.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, textAlign: 'left' }}>
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => onPick(s)}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px',
                background: 'var(--gray-0)', border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-xs)', cursor: 'pointer',
                fontFamily: 'var(--font-sans)', fontSize: 13.5, color: 'var(--text-body)', textAlign: 'left',
                transition: 'border-color var(--dur-fast) var(--ease-out), box-shadow var(--dur-fast) var(--ease-out)',
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'var(--blue-300)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border-subtle)'; e.currentTarget.style.boxShadow = 'var(--shadow-xs)'; }}>
              <span style={{ color: 'var(--blue-400)', flex: 'none', display: 'inline-flex' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
              </span>
              <span>{s}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

window.EmptyState = EmptyState;
