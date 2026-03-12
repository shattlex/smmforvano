import sqlite3
from contextlib import contextmanager
from typing import Iterable, Sequence

from app.config import DATABASE_URL, DB_PATH

try:
  import psycopg
  from psycopg.rows import dict_row
except Exception:  # pragma: no cover
  psycopg = None
  dict_row = None


def _is_postgres() -> bool:
  return DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")


def _sqlite_path() -> str:
  if DATABASE_URL.startswith("sqlite:///"):
    return DATABASE_URL.replace("sqlite:///", "", 1)
  return str(DB_PATH)


def _normalize_query(query: str) -> str:
  if _is_postgres():
    return query.replace("?", "%s")
  return query


SQLITE_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS seeds (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  seed_name TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  app_password TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS campaigns (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_name TEXT NOT NULL,
  cid_token TEXT,
  subject TEXT NOT NULL,
  date_from TEXT,
  date_to TEXT,
  window_hours INTEGER,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at_utc TEXT NOT NULL,
  finished_at_utc TEXT,
  status TEXT NOT NULL,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS run_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  campaign_id INTEGER NOT NULL,
  seed_id INTEGER NOT NULL,
  status TEXT NOT NULL,
  found_folder TEXT,
  found_count INTEGER NOT NULL DEFAULT 0,
  latest_message_utc TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (run_id, campaign_id, seed_id),
  FOREIGN KEY(run_id) REFERENCES runs(id),
  FOREIGN KEY(campaign_id) REFERENCES campaigns(id),
  FOREIGN KEY(seed_id) REFERENCES seeds(id)
);
"""


POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_active SMALLINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS seeds (
  id BIGSERIAL PRIMARY KEY,
  seed_name TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL UNIQUE,
  app_password TEXT NOT NULL,
  is_active SMALLINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaigns (
  id BIGSERIAL PRIMARY KEY,
  campaign_name TEXT NOT NULL,
  cid_token TEXT,
  subject TEXT NOT NULL,
  date_from DATE,
  date_to DATE,
  window_hours INTEGER,
  is_active SMALLINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runs (
  id BIGSERIAL PRIMARY KEY,
  started_at_utc TEXT NOT NULL,
  finished_at_utc TEXT,
  status TEXT NOT NULL,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS run_results (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES runs(id),
  campaign_id BIGINT NOT NULL REFERENCES campaigns(id),
  seed_id BIGINT NOT NULL REFERENCES seeds(id),
  status TEXT NOT NULL,
  found_folder TEXT,
  found_count INTEGER NOT NULL DEFAULT 0,
  latest_message_utc TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (run_id, campaign_id, seed_id)
);
"""


@contextmanager
def connect():
  if _is_postgres():
    if psycopg is None:
      raise RuntimeError("psycopg is required for PostgreSQL. Install from requirements.txt")
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
      yield conn
    finally:
      conn.close()
  else:
    path = _sqlite_path()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
      yield conn
    finally:
      conn.close()


def init_db() -> None:
  with connect() as conn:
    if _is_postgres():
      conn.execute(POSTGRES_SCHEMA)
    else:
      conn.executescript(SQLITE_SCHEMA)
    conn.commit()


def execute(query: str, params: Sequence = ()) -> None:
  with connect() as conn:
    conn.execute(_normalize_query(query), params)
    conn.commit()


def executemany(query: str, rows: Iterable[Sequence]) -> None:
  with connect() as conn:
    cur = conn.cursor()
    cur.executemany(_normalize_query(query), rows)
    conn.commit()


def fetch_all(query: str, params: Sequence = ()): 
  with connect() as conn:
    rows = conn.execute(_normalize_query(query), params).fetchall()
    if _is_postgres():
      return rows
    return rows


def fetch_one(query: str, params: Sequence = ()): 
  with connect() as conn:
    return conn.execute(_normalize_query(query), params).fetchone()
