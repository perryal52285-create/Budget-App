"""SQLite persistence for Perry Budget. Money stored as integer cents.

Definitions (earners, income_sources, bills, debts) are the recurring TEMPLATE.
Per-month actuals (paycheck_actuals, bill_payments, debt_snapshots) retain history,
so editing the template never rewrites the past.
"""
import os
import sqlite3
from contextlib import contextmanager

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "perry_budget.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS earners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#e3b341',
    is_primary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS income_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    earner_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    employer TEXT DEFAULT '',                   -- employer / payer name
    kind TEXT NOT NULL DEFAULT 'payroll',      -- payroll|reimbursement|bonus_annual|one_time|other
    amount_cents INTEGER NOT NULL DEFAULT 0,
    frequency TEXT NOT NULL DEFAULT 'biweekly', -- weekly|biweekly|semimonthly|monthly|annual|one_time
    anchor_date TEXT DEFAULT '',                -- ISO date for weekly/biweekly/one_time
    day1 INTEGER NOT NULL DEFAULT 1,            -- semimonthly/monthly/annual day (0 = last day)
    day2 INTEGER NOT NULL DEFAULT 0,            -- semimonthly second day (0 = last day)
    month INTEGER NOT NULL DEFAULT 1,           -- annual month
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    amount_cents INTEGER NOT NULL DEFAULT 0,
    due_dom INTEGER NOT NULL DEFAULT 1,         -- day of month due
    category TEXT DEFAULT '',
    autopay INTEGER NOT NULL DEFAULT 0,
    where_to_pay TEXT DEFAULT '',
    responsible_earner_id INTEGER DEFAULT NULL, -- NULL = joint
    funding_mode TEXT NOT NULL DEFAULT 'auto',  -- auto|manual
    funding_source_id INTEGER DEFAULT NULL,
    funding_occurrence INTEGER DEFAULT NULL
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

CREATE TABLE IF NOT EXISTS paycheck_actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    occurrence INTEGER NOT NULL,
    pay_date TEXT DEFAULT '',
    amount_cents INTEGER NOT NULL DEFAULT 0,
    motus_cents INTEGER NOT NULL DEFAULT 0,
    note TEXT DEFAULT '',
    UNIQUE(year, month, source_id, occurrence)
);

CREATE TABLE IF NOT EXISTS bill_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    bill_id INTEGER NOT NULL,
    paid_cents INTEGER NOT NULL DEFAULT 0,
    paid INTEGER NOT NULL DEFAULT 0,
    funding_source_id INTEGER DEFAULT NULL,
    funding_occurrence INTEGER DEFAULT NULL,
    UNIQUE(year, month, bill_id)
);

CREATE TABLE IF NOT EXISTS debt_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    debt_id INTEGER NOT NULL,
    balance_cents INTEGER NOT NULL DEFAULT 0,
    UNIQUE(year, month, debt_id)
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    monthly_limit_cents INTEGER NOT NULL DEFAULT 0,
    UNIQUE(category)
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    category TEXT DEFAULT '',
    description TEXT DEFAULT '',
    amount_cents INTEGER NOT NULL DEFAULT 0,
    txn_date TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT DEFAULT '',
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    earner_id INTEGER DEFAULT NULL,        -- links a login to an earner profile
    theme TEXT DEFAULT '',                  -- per-user default theme override
    created_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

-- Net-worth tracking: accounts + dated balance snapshots.
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'checking',  -- checking|savings|investment|cash|property|loan|credit|other
    is_liability INTEGER NOT NULL DEFAULT 0,
    institution TEXT DEFAULT '',
    owner_earner_id INTEGER DEFAULT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS account_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    as_of TEXT NOT NULL,                     -- ISO date
    balance_cents INTEGER NOT NULL DEFAULT 0,
    UNIQUE(account_id, as_of)
);
"""


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)
    _migrate()
    _seed()
    _seed_users()


# Additive schema migrations: (table, column, column-def). CREATE TABLE IF NOT
# EXISTS never alters an existing table, so new columns are added here so HA
# databases that persist across rebuilds pick them up.
_MIGRATIONS = [
    ("income_sources", "employer", "TEXT DEFAULT ''"),
    # bills columns added after Phase 1 (old DBs only had due_day/assignment)
    ("bills", "due_dom", "INTEGER NOT NULL DEFAULT 1"),
    ("bills", "category", "TEXT DEFAULT ''"),
    ("bills", "autopay", "INTEGER NOT NULL DEFAULT 0"),
    ("bills", "where_to_pay", "TEXT DEFAULT ''"),
    ("bills", "responsible_earner_id", "INTEGER DEFAULT NULL"),
    ("bills", "funding_mode", "TEXT NOT NULL DEFAULT 'auto'"),
    ("bills", "funding_source_id", "INTEGER DEFAULT NULL"),
    ("bills", "funding_occurrence", "INTEGER DEFAULT NULL"),
]


def _migrate():
    with connect() as con:
        for table, column, coldef in _MIGRATIONS:
            cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            if column not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")


def _seed():
    """First-run defaults only (skips if earners already exist)."""
    if query("SELECT 1 FROM earners LIMIT 1"):
        return
    set_setting("timezone", "America/Chicago")
    alex = execute("INSERT INTO earners (name, color, is_primary) VALUES (?,?,1)", ("Alex", "#46d970"))
    execute("INSERT INTO earners (name, color, is_primary) VALUES (?,?,0)", ("Rae", "#ff79b0"))
    execute(
        "INSERT INTO income_sources (earner_id, name, kind, amount_cents, frequency, anchor_date)"
        " VALUES (?,?,?,?,?,?)",
        (alex, "Alex Payroll", "payroll", 0, "biweekly", "2026-06-05"))
    execute(
        "INSERT INTO income_sources (earner_id, name, kind, amount_cents, frequency)"
        " VALUES (?,?,?,?,?)",
        (alex, "Motus Reimbursement", "reimbursement", 0, "monthly"))
    execute(
        "INSERT INTO income_sources (earner_id, name, kind, amount_cents, frequency, month, day1)"
        " VALUES (?,?,?,?,?,?,?)",
        (alex, "January Bonus", "bonus_annual", 0, "annual", 1, 15))


def _seed_users():
    """Create the two logins (Alex, Rae) on first run, linked to their earner
    profiles by name. Runs independently of _seed so it also bootstraps existing
    databases that predate auth. Default password is a throwaway that must be
    changed on first login."""
    if query("SELECT 1 FROM users LIMIT 1"):
        return
    # Imported lazily to avoid a circular import at module load.
    from . import auth
    import time
    earners = {e["name"].lower(): e["id"] for e in query("SELECT id, name FROM earners")}
    for username, display in (("alex", "Alex"), ("rae", "Rae")):
        salt, h = auth.hash_password(auth.DEFAULT_PASSWORD)
        execute(
            "INSERT INTO users (username, display_name, password_salt, password_hash,"
            " must_change_password, earner_id, created_at) VALUES (?,?,?,?,?,?,?)",
            (username, display, salt, h, 1, earners.get(username), int(time.time())))


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


# ---- settings helpers ----------------------------------------------------

def get_setting(key, default=None):
    rows = query("SELECT value FROM settings WHERE key=?", (key,))
    return rows[0]["value"] if rows else default


def set_setting(key, value):
    execute("INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
