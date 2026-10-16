"""
Shared database for MarketPlayground v4.

Every user's beliefs, picks, market grades, feedback and trained network
versions live here, so the system learns from all users together.

- Production: set DATABASE_URL to a Postgres URL (e.g. a Render Postgres
  database). Render wipes local files on each deploy, so Postgres is required
  for learning to persist there.
- Local/dev: with no DATABASE_URL, a SQLite file is used
  (MP_SQLITE_PATH, default backend/v4/data/marketplayground.db).

The layer is intentionally tiny: write SQL with `?` placeholders and it is
converted for Postgres automatically.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Optional

_DEFAULT_SQLITE = os.path.join(os.path.dirname(__file__), "data", "marketplayground.db")
_lock = threading.RLock()
_initialized: set[str] = set()


def _url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def is_postgres() -> bool:
    u = _url()
    return u.startswith("postgres://") or u.startswith("postgresql://")


@contextmanager
def connect():
    """Yield a DB-API connection; commits on success, rolls back on error."""
    if is_postgres():
        import psycopg  # psycopg 3

        url = _url().replace("postgres://", "postgresql://", 1)
        conn = psycopg.connect(url)
    else:
        path = os.getenv("MP_SQLITE_PATH", _DEFAULT_SQLITE)
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if is_postgres() else sql


def execute(sql: str, params: Iterable[Any] = ()) -> None:
    ensure_schema()
    with _lock, connect() as conn:
        cur = conn.cursor()
        cur.execute(_sql(sql), tuple(params))


def executemany(sql: str, rows: Iterable[Iterable[Any]]) -> None:
    rows = [tuple(r) for r in rows]
    if not rows:
        return
    ensure_schema()
    with _lock, connect() as conn:
        cur = conn.cursor()
        cur.executemany(_sql(sql), rows)


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    ensure_schema()
    with _lock, connect() as conn:
        cur = conn.cursor()
        cur.execute(_sql(sql), tuple(params))
        if cur.description is None:
            return []
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[dict]:
    rows = query(sql, params)
    return rows[0] if rows else None


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, separators=(",", ":"))


def loads(s: Any, default: Any = None) -> Any:
    if s is None or s == "":
        return default
    if isinstance(s, (dict, list)):
        return s
    try:
        return json.loads(s)
    except Exception:
        return default


def _schema() -> list[str]:
    blob = "BYTEA" if is_postgres() else "BLOB"
    return [
        """CREATE TABLE IF NOT EXISTS beliefs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            norm_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            source TEXT NOT NULL,
            risk_profile TEXT,
            direction TEXT,
            horizon_days INTEGER,
            conviction TEXT,
            themes TEXT,
            interpretation TEXT,
            model TEXT,
            cost_usd REAL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_beliefs_norm ON beliefs(norm_text)",
        "CREATE INDEX IF NOT EXISTS ix_beliefs_asof ON beliefs(as_of_date)",
        """CREATE TABLE IF NOT EXISTS picks (
            id TEXT PRIMARY KEY,
            belief_id TEXT NOT NULL REFERENCES beliefs(id),
            ticker TEXT NOT NULL,
            name TEXT,
            exposure TEXT,
            direction TEXT NOT NULL,
            rationale TEXT,
            claude_rank INTEGER,
            claude_score REAL,
            nn_score REAL,
            final_score REAL,
            final_rank INTEGER,
            shown INTEGER NOT NULL DEFAULT 0,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            structure TEXT,
            legs TEXT,
            features TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_picks_belief ON picks(belief_id)",
        "CREATE INDEX IF NOT EXISTS ix_picks_ticker ON picks(ticker)",
        """CREATE TABLE IF NOT EXISTS pick_themes (
            pick_id TEXT NOT NULL REFERENCES picks(id),
            theme TEXT NOT NULL,
            PRIMARY KEY (pick_id, theme)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_pick_themes_theme ON pick_themes(theme)",
        """CREATE TABLE IF NOT EXISTS outcomes (
            pick_id TEXT NOT NULL REFERENCES picks(id),
            checkpoint_days INTEGER NOT NULL,
            eval_date TEXT NOT NULL,
            price REAL NOT NULL,
            ret REAL NOT NULL,
            spy_ret REAL NOT NULL,
            dir_excess REAL NOT NULL,
            structure_ret REAL,
            graded_at TEXT NOT NULL,
            PRIMARY KEY (pick_id, checkpoint_days)
        )""",
        """CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            belief_id TEXT NOT NULL,
            pick_id TEXT,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_feedback_pick ON feedback(pick_id)",
        f"""CREATE TABLE IF NOT EXISTS nn_models (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            n_train INTEGER NOT NULL,
            n_test INTEGER NOT NULL,
            metrics TEXT,
            blob {blob} NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS kv_cache (
            k TEXT PRIMARY KEY,
            v TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
    ]


def ensure_schema() -> None:
    key = _url() or os.getenv("MP_SQLITE_PATH", _DEFAULT_SQLITE)
    if key in _initialized:
        return
    with _lock:
        if key in _initialized:
            return
        with connect() as conn:
            cur = conn.cursor()
            for stmt in _schema():
                cur.execute(stmt)
        _initialized.add(key)


def reset_for_tests() -> None:
    _initialized.clear()
