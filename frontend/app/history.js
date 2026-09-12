/* Chat history persistence — Phase 2 (local SQLite on the backend).

   Exposed as window.QMS_History behind the same interface as Phase 1
   (list / load / save / remove / newId), so App.jsx and the Sidebar are
   unchanged apart from awaiting the now-async calls. Storage moved from the
   browser's localStorage to a sqlite file the FastAPI backend owns
   (GET/PUT/DELETE /conversations), so history survives a cleared browser cache
   and is shared across browsers on the machine. Still 100% local — the backend
   opens a local file; nothing leaves the machine.

   All network calls fail soft (empty list / null / false) so a backend that's
   down degrades to "no history" rather than throwing in the UI. */
(function () {
  const API = (window.QMS_CONFIG && window.QMS_CONFIG.API_BASE) || '';

  // Relative bucket for the sidebar grouping (mirrors the old static labels).
  function _bucket(ts) {
    const day = 24 * 60 * 60 * 1000;
    const startOf = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    const diff = Math.round((startOf(new Date()) - startOf(new Date(ts))) / day);
    if (diff <= 0) return 'Today';
    if (diff === 1) return 'Yesterday';
    if (diff < 7) return 'This week';
    return 'Older';
  }

  function newId() {
    return 'c' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }

  // -> Promise<[{ id, title, updatedAt, when }]>, newest first (backend orders).
  async function list() {
    try {
      const r = await fetch(API + '/conversations');
      if (!r.ok) return [];
      const d = await r.json();
      return (d.conversations || []).map((c) => ({
        id: c.id,
        title: c.title || 'Untitled chat',
        updatedAt: c.updated_at,
        when: _bucket(c.updated_at),
      }));
    } catch (e) { return []; }
  }

  // -> Promise<{ title, messages, docsById, summary, summarizedCount } | null>.
  async function load(id) {
    try {
      const r = await fetch(`${API}/conversations/${id}`);
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  // -> Promise<boolean>.
  async function save(id, data) {
    try {
      const r = await fetch(`${API}/conversations/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      return r.ok;
    } catch (e) { return false; }
  }

  // -> Promise<void>.
  async function remove(id) {
    try { await fetch(`${API}/conversations/${id}`, { method: 'DELETE' }); } catch (e) { /* ignore */ }
  }

  window.QMS_History = { list, load, save, remove, newId };
})();
