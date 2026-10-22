import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .tools import TOOLS

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool TEXT NOT NULL,
  ref TEXT NOT NULL,
  status TEXT NOT NULL,
  data TEXT NOT NULL,
  submitted_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(tool, ref)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tool TEXT NOT NULL,
  record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  reason TEXT,
  from_status TEXT,
  to_status TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_records_tool ON records(tool);
CREATE INDEX IF NOT EXISTS idx_events_record ON events(tool, record_id);
"""


def db_path() -> str:
    return os.environ.get("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "app.db"))


def now_iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    path = db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(seed_if_empty: bool = True) -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        if seed_if_empty:
            for key in TOOLS:
                n = conn.execute("SELECT COUNT(*) FROM records WHERE tool=?", (key,)).fetchone()[0]
                if n == 0:
                    _seed_tool(conn, key)
    finally:
        conn.close()


def reset_tool(key: str) -> None:
    """Delete and reseed records/history for ONE tool only."""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM events WHERE tool=?", (key,))
        conn.execute("DELETE FROM records WHERE tool=?", (key,))
        _seed_tool(conn, key, in_tx=True)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def _seed_tool(conn: sqlite3.Connection, key: str, in_tx: bool = False) -> None:
    tool = TOOLS[key]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if not in_tx:
        conn.execute("BEGIN IMMEDIATE")
    for item in tool.seed():
        submitted = now - timedelta(hours=item["hours_ago"])
        cur = conn.execute(
            "INSERT INTO records(tool, ref, status, data, submitted_at, updated_at) VALUES (?,?,?,?,?,?)",
            (key, item["ref"], item["status"], json.dumps(item["data"]), now_iso(submitted), now_iso(submitted)),
        )
        rid = cur.lastrowid
        conn.execute(
            "INSERT INTO events(tool, record_id, action, actor, actor_role, reason, from_status, to_status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (key, rid, "submitted", item["data"].get(tool.requester_field, "system"), "requester", None, None, "pending", now_iso(submitted)),
        )
        d = item.get("decision")
        if d:
            at = submitted + timedelta(hours=d["hours_after_submit"])
            conn.execute(
                "INSERT INTO events(tool, record_id, action, actor, actor_role, reason, from_status, to_status, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (key, rid, d["action"], d["actor"], "reviewer", d["reason"], "pending", item["status"], now_iso(at)),
            )
            conn.execute("UPDATE records SET updated_at=? WHERE id=?", (now_iso(at), rid))
    if not in_tx:
        conn.execute("COMMIT")
