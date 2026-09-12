"""Chat-history persistence — Phase 2 (local SQLite).

Backs the same conversation interface the frontend's history.js exposes, but on
the backend so history survives a cleared browser cache, is shared across browsers
on the machine, and is backup-able. SQLite is serverless — just a file the FastAPI
process opens through the stdlib ``sqlite3`` module; no extra process, no new
dependency, nothing leaves the machine.

Messages and their cited source docs are stored as JSON blobs (they're read and
written whole, per conversation); conversation-level fields (title, updated_at)
are real columns so the sidebar list is a cheap indexed query.
"""
import json
import os
import sqlite3
import time

# Overridable so tests can point at a temp file instead of the real DB.
DB_PATH = os.getenv(
    "HISTORY_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "history.db"),
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id               TEXT PRIMARY KEY,
    title            TEXT,
    updated_at       INTEGER,
    summary          TEXT,
    summarized_count INTEGER,
    messages         TEXT,   -- JSON array
    docs             TEXT    -- JSON object (docsById)
);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
"""


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def list_conversations() -> list[dict]:
    """[{id, title, updated_at}], newest first — the sidebar list."""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [{"id": r["id"], "title": r["title"], "updated_at": r["updated_at"]} for r in rows]


def get_conversation(cid: str) -> dict | None:
    """Full thread in the shape the frontend saved, or None if unknown."""
    conn = _connect()
    try:
        r = conn.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
    finally:
        conn.close()
    if not r:
        return None
    return {
        "id": r["id"],
        "title": r["title"],
        "updated_at": r["updated_at"],
        "summary": r["summary"] or "",
        "summarizedCount": r["summarized_count"] or 0,
        "messages": json.loads(r["messages"] or "[]"),
        "docsById": json.loads(r["docs"] or "{}"),
    }


def save_conversation(cid: str, data: dict) -> int:
    """Upsert a conversation. Returns the stored updated_at (ms epoch)."""
    updated_at = int(data.get("updatedAt") or time.time() * 1000)
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO conversations (id, title, updated_at, summary, summarized_count, messages, docs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title            = excluded.title,
                updated_at       = excluded.updated_at,
                summary          = excluded.summary,
                summarized_count = excluded.summarized_count,
                messages         = excluded.messages,
                docs             = excluded.docs
            """,
            (
                cid,
                data.get("title") or "Adsız sohbet",
                updated_at,
                data.get("summary") or "",
                int(data.get("summarizedCount") or 0),
                json.dumps(data.get("messages") or [], ensure_ascii=False),
                json.dumps(data.get("docsById") or {}, ensure_ascii=False),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return updated_at


def delete_conversation(cid: str) -> None:
    conn = _connect()
    try:
        conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
        conn.commit()
    finally:
        conn.close()
