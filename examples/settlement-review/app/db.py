import os
import sqlite3
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS exceptions (
  id TEXT PRIMARY KEY, tenant TEXT NOT NULL, reference TEXT NOT NULL, counterparty TEXT NOT NULL,
  amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, exception_type TEXT NOT NULL,
  account_number TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS history (
  id INTEGER PRIMARY KEY AUTOINCREMENT, exception_id TEXT NOT NULL, tenant TEXT NOT NULL,
  actor TEXT NOT NULL, action TEXT NOT NULL, reason TEXT, from_status TEXT, to_status TEXT, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY, username TEXT NOT NULL, csrf TEXT NOT NULL, expires_at REAL NOT NULL);
"""

# All synthetic. Account numbers are fictional.
SEED = [
    ("SE-1001", "tenant-a", "STL-A-7781", "Harbor Coffee Co (fictional)", 128450, "USD", "Amount mismatch", "GB00DEMO00001234"),
    ("SE-1002", "tenant-a", "STL-A-7790", "Maple Freight Ltd (fictional)", 990000, "USD", "Duplicate settlement", "GB00DEMO00005678"),
    ("SE-1003", "tenant-a", "STL-A-7802", "Kestrel Books (fictional)", 4520, "USD", "Late cut-off", "GB00DEMO00009012"),
    ("SE-1004", "tenant-a", "STL-A-7815", "Juniper Health Clinic (fictional)", 310075, "USD", "Beneficiary changed", "GB00DEMO00003456"),
    ("SE-2001", "tenant-b", "STL-B-3301", "Orchid Travel (fictional)", 77000, "EUR", "Amount mismatch", "DE00DEMO00007777"),
    ("SE-2002", "tenant-b", "STL-B-3315", "Quarry Tools GmbH (fictional)", 1520000, "EUR", "Missing remittance", "DE00DEMO00008888"),
    ("SE-2003", "tenant-b", "STL-B-3320", "Lumen Studio (fictional)", 21999, "EUR", "Late cut-off", "DE00DEMO00009999"),
]


def db_path() -> str:
    return os.environ.get("SR_DB", os.path.join(os.path.dirname(__file__), "..", "data", "settlement.db"))


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init(path: str | None = None, reset: bool = False) -> None:
    conn = connect(path)
    if reset:
        conn.executescript("DROP TABLE IF EXISTS exceptions; DROP TABLE IF EXISTS history; DROP TABLE IF EXISTS sessions;")
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM exceptions").fetchone()[0] == 0:
        base = datetime.now(timezone.utc)
        for i, row in enumerate(SEED):
            conn.execute("INSERT INTO exceptions (id, tenant, reference, counterparty, amount_cents, currency, exception_type,"
                         " account_number, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                         (*row, (base - timedelta(hours=3 * i + 1)).isoformat(timespec="seconds")))
    conn.close()
