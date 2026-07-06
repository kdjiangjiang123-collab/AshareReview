"""Database schema and initialization for A-Share Review Tool."""

import sqlite3
from config.settings import DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date      TEXT NOT NULL,
    trade_type      TEXT NOT NULL CHECK(trade_type IN ('buy', 'sell')),
    stock_code      TEXT NOT NULL,
    stock_name      TEXT NOT NULL,
    price           REAL NOT NULL,
    quantity        INTEGER NOT NULL,
    amount          REAL NOT NULL,
    reason          TEXT,
    logic           TEXT,
    profit_loss     REAL,
    profit_loss_pct REAL,
    tags            TEXT DEFAULT '[]',
    review_notes    TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_code ON trades(stock_code);
CREATE INDEX IF NOT EXISTS idx_trades_type ON trades(trade_type);

CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code      TEXT NOT NULL,
    stock_name      TEXT NOT NULL,
    cost_price      REAL NOT NULL,
    quantity        INTEGER NOT NULL,
    buy_date        TEXT NOT NULL,
    current_price   REAL,
    pnl_pct         REAL,
    notes           TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_holdings_active ON holdings(is_active);

CREATE TABLE IF NOT EXISTS intraday_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time   TEXT NOT NULL,
    index_data      TEXT,
    breadth_data    TEXT,
    sector_data     TEXT,
    north_flow      TEXT,
    holdings_snapshot TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   TEXT NOT NULL UNIQUE,
    indices         TEXT,
    breadth         TEXT,
    limit_up        TEXT,
    north_bound     TEXT,
    sectors         TEXT,
    raw_data        TEXT,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS ai_analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date   TEXT NOT NULL,
    analysis_type   TEXT NOT NULL CHECK(analysis_type IN ('intraday', 'aftermarket')),
    model_used      TEXT NOT NULL,
    analysis_json   TEXT NOT NULL,
    user_rating     INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_analyses_date ON ai_analyses(analysis_date);
CREATE INDEX IF NOT EXISTS idx_analyses_type ON ai_analyses(analysis_type);
"""


def init_db() -> sqlite3.Connection:
    """Initialize database and return a connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_connection() -> sqlite3.Connection:
    """Get a database connection. Creates tables if not exists."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
