import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    expected_amount TEXT NOT NULL,
    state TEXT NOT NULL,
    product_id TEXT,
    paid_amount TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS inventory (
    product_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price TEXT NOT NULL,
    stock INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    transaction_id TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    metadata TEXT NOT NULL
);
"""


def create_connection(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
