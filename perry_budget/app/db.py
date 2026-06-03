"""SQLite persistence for Perry Budget. Money stored as integer cents."""
import os
import sqlite3
from contextlib import contextmanager

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "perry_budget.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS paychecks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,              -- "14th" or "28th"
    net_cents INTEGER NOT NULL DEFAULT 0,
    motus_cents INTEGER NOT NULL DEFAULT 0,
    other_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    due_day TEXT DEFAULT '',
    category TEXT DEFAULT '',
    autopay INTEGER NOT NULL DEFAULT 0,
    where_to_pay TEXT DEFAULT '',
    assignment TEXT NOT NULL DEFAULT '14th'  -- "14th" | "28th"
);
CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    balance_cents INTEGER NOT NULL DEFAULT 0,
    min_payment_cents INTEGER NOT NULL DEFAULT 0,
    apr REAL NOT NULL DEFAULT 0.0,
    roll_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_cents INTEGER NOT NULL DEFAULT 0,
    current_cents INTEGER NOT NULL DEFAULT 0,
    target_date TEXT DEFAULT ''
);
"""


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)


@contextmanager
def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def query(sql, params=()):
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def execute(sql, params=()):
    with connect() as con:
        cur = con.execute(sql, params)
        return cur.lastrowid
