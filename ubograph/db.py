"""SQLite persistence for cases, the watchlist, and the activity log.

Render's free tier has no managed database and this app has otherwise been
entirely stateless (one request in, one response out) — a single SQLite file
on local disk is the simplest thing that actually works there, and gunicorn's
worker processes share it safely (SQLite handles concurrent access from
multiple processes on its own). The one honest limit: it does NOT survive a
redeploy or the free tier's spin-down-to-zero — the filesystem resets each
time. Fine for a single-user workspace; not a system of record for real
casework without a real, persistent database behind it.
"""
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).resolve().parent / "data" / "sanctionsplus.db"


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_name TEXT,
            payload TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL DEFAULT 'any',
            nationality TEXT,
            birth_date TEXT,
            last_flags TEXT NOT NULL DEFAULT '[]',
            last_band TEXT,
            last_checked_at REAL,
            created_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at REAL NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


def log_activity(action: str, detail: str = "") -> None:
    conn = _connect()
    conn.execute("INSERT INTO activity_log (at, action, detail) VALUES (?, ?, ?)",
                 (time.time(), action, detail))
    conn.commit()
    conn.close()


def recent_activity(limit: int = 200) -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, at, action, detail FROM activity_log ORDER BY at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- cases ------------------------------------------------------------

def save_case(name: str, node_id: str, node_name: str, payload: dict, notes: str = "") -> int:
    now = time.time()
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO cases (name, node_id, node_name, payload, notes, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, node_id, node_name, json.dumps(payload), notes, now, now),
    )
    conn.commit()
    case_id = cur.lastrowid
    conn.close()
    log_activity("case_saved", f"#{case_id} {name} — {node_name}")
    return case_id


def list_cases() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT id, name, node_id, node_name, notes, created_at, updated_at "
        "FROM cases ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_case(case_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    conn.close()
    if not row:
        return None
    case = dict(row)
    case["payload"] = json.loads(case["payload"])
    return case


def update_case_notes(case_id: int, notes: str) -> bool:
    conn = _connect()
    cur = conn.execute(
        "UPDATE cases SET notes = ?, updated_at = ? WHERE id = ?", (notes, time.time(), case_id)
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    if changed:
        log_activity("case_updated", f"#{case_id}")
    return changed


def delete_case(case_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    if changed:
        log_activity("case_deleted", f"#{case_id}")
    return changed


# --- watchlist ----------------------------------------------------------

def add_watch(name: str, entity_type: str = "any", nationality: str = None,
              birth_date: str = None) -> int:
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO watchlist (name, entity_type, nationality, birth_date, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, entity_type, nationality, birth_date, time.time()),
    )
    conn.commit()
    watch_id = cur.lastrowid
    conn.close()
    log_activity("watch_added", name)
    return watch_id


def list_watches() -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM watchlist ORDER BY created_at DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["last_flags"] = json.loads(d["last_flags"] or "[]")
        out.append(d)
    return out


def get_watch(watch_id: int) -> Optional[dict]:
    conn = _connect()
    row = conn.execute("SELECT * FROM watchlist WHERE id = ?", (watch_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["last_flags"] = json.loads(d["last_flags"] or "[]")
    return d


def update_watch_result(watch_id: int, flags: list, band: Optional[str]) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE watchlist SET last_flags = ?, last_band = ?, last_checked_at = ? WHERE id = ?",
        (json.dumps(flags), band, time.time(), watch_id),
    )
    conn.commit()
    conn.close()


def delete_watch(watch_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    if changed:
        log_activity("watch_removed", f"#{watch_id}")
    return changed
