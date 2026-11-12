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


def _sql(sql: str, has_params: bool = True) -> str:
    """Write SQL with `?` placeholders; for Postgres, convert to %s and escape literal %."""
    if not is_postgres():
        return sql
    if not has_params:
        return sql  # no parameters: psycopg leaves % alone
    return sql.replace("%", "%%").replace("?", "%s")


def _clean(v: Any) -> Any:
    """Postgres text can't hold NUL bytes (it raises); they're never meaningful here, so drop them."""
    return v.replace("\x00", "") if isinstance(v, str) else v


def _run(cur, sql: str, params: Iterable[Any]) -> None:
    params = tuple(_clean(p) for p in params)
    if params:
        cur.execute(_sql(sql), params)
    else:
        cur.execute(_sql(sql, has_params=False))


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """Run one statement; returns the number of rows it changed."""
    ensure_schema()
    with _lock, connect() as conn:
        cur = conn.cursor()
        _run(cur, sql, params)
        return int(cur.rowcount or 0) if cur.rowcount is not None and cur.rowcount >= 0 else 0


def executemany(sql: str, rows: Iterable[Iterable[Any]]) -> None:
    rows = [tuple(_clean(v) for v in r) for r in rows]
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
        _run(cur, sql, params)
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
        "CREATE INDEX IF NOT EXISTS ix_beliefs_user ON beliefs(user_id)",
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
        "CREATE INDEX IF NOT EXISTS ix_beliefs_created ON beliefs(created_at)",
        "CREATE INDEX IF NOT EXISTS ix_beliefs_source ON beliefs(source)",
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
        "CREATE INDEX IF NOT EXISTS ix_outcomes_graded ON outcomes(graded_at)",
        "CREATE INDEX IF NOT EXISTS ix_outcomes_checkpoint ON outcomes(checkpoint_days)",
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
        """CREATE TABLE IF NOT EXISTS waitlist (
            email TEXT PRIMARY KEY,
            belief TEXT,
            source TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            uid TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            name TEXT,
            pw_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_login TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS email_tokens (
            token_hash TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_sessions_account ON sessions(account_id)",
        """CREATE TABLE IF NOT EXISTS passkeys (
            credential_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            public_key TEXT NOT NULL,
            sign_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_used TEXT,
            label TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_passkeys_account ON passkeys(account_id)",
        """CREATE TABLE IF NOT EXISTS broker_links (
            account_id TEXT PRIMARY KEY,
            broker TEXT NOT NULL,
            env TEXT NOT NULL,
            token_enc TEXT NOT NULL,
            connected_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS broker_orders (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            env TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            ticker TEXT NOT NULL,
            side TEXT NOT NULL,
            notional REAL NOT NULL,
            est_price REAL,
            belief_id TEXT,
            pick_id TEXT,
            request TEXT,
            response TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS strategists (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            style TEXT NOT NULL,
            gen INTEGER NOT NULL,
            parent_id TEXT,
            weights TEXT NOT NULL,
            status TEXT NOT NULL,
            fitness REAL,
            beat_rate REAL,
            n_scored INTEGER,
            born_at TEXT NOT NULL,
            retired_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS lineage_events (
            id TEXT PRIMARY KEY,
            at TEXT NOT NULL,
            kind TEXT NOT NULL,
            strategist_id TEXT NOT NULL,
            detail TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS broker_exits (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            env TEXT NOT NULL,
            symbol TEXT NOT NULL,
            kind TEXT NOT NULL,
            held_at TEXT NOT NULL,
            status TEXT NOT NULL,
            qty REAL,
            source_order TEXT,
            entry REAL,
            tp_pct REAL,
            sl_pct REAL,
            tp_price REAL,
            sl_price REAL,
            stop_order TEXT,
            stop_day TEXT,
            sell_order TEXT,
            sell_sent_at TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS option_vol_daily (
            day TEXT NOT NULL,
            underlying TEXT NOT NULL,
            spot REAL,
            atm_iv REAL,
            atm_days INTEGER,
            rv20 REAL,
            rv60 REAL,
            put_call_skew REAL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (day, underlying)
        )""",
        """CREATE TABLE IF NOT EXISTS yesno_calls (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            level REAL NOT NULL,
            expiration TEXT NOT NULL,
            side TEXT NOT NULL,
            market_p REAL NOT NULL,
            brain_p REAL NOT NULL,
            spot REAL,
            strikes TEXT,
            cost REAL,
            payout REAL,
            contracts INTEGER,
            position_id TEXT,
            created_at TEXT NOT NULL,
            close_price REAL,
            above INTEGER,
            graded_at TEXT,
            features TEXT
        )""",
        "CREATE INDEX IF NOT EXISTS ix_yesno_user ON yesno_calls(user_id)",
        """CREATE TABLE IF NOT EXISTS feature_log (
            id TEXT PRIMARY KEY,
            feature TEXT NOT NULL,
            subject TEXT NOT NULL,
            pick_id TEXT,
            as_of TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""",
        "CREATE INDEX IF NOT EXISTS ix_feature_log_pick ON feature_log(pick_id)",
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
        # On Postgres every DDL statement here waits for a table lock, even when the table, index or column
        # already exists. Behind one long-running query that wait was unbounded: on 2026-11-09 a 44-minute ad-hoc
        # SELECT on picks left "ALTER TABLE picks ADD COLUMN spy_entry" queued, every later query on picks queued
        # behind it, and the web service hung at startup (502s) until the SELECT was cancelled. So: bounded lock
        # waits, and migrations whose column is already there are skipped without taking a lock.
        try:
            with connect() as conn:
                cur = conn.cursor()
                _bound_lock_wait(cur)
                for stmt in _schema():
                    cur.execute(stmt)
        except Exception as e:
            if not is_postgres():
                raise
            print(f"[db] schema in one pass failed ({e}); retrying statement by statement")
            for stmt in _schema():
                try:
                    with connect() as conn:
                        cur = conn.cursor()
                        _bound_lock_wait(cur)
                        cur.execute(stmt)
                except Exception as e2:
                    print(f"[db] schema statement skipped ({e2}): {stmt.split(chr(10))[0][:80]}")
        have = _pg_columns() if is_postgres() else None
        # additive migrations for tables that already exist (each in its own transaction; "already there" is fine)
        for stmt in _migrations():
            tc = _migration_target(stmt)
            if have is not None and tc is not None and tc in have:
                continue
            try:
                with connect() as conn:
                    cur = conn.cursor()
                    _bound_lock_wait(cur)
                    cur.execute(stmt)
            except Exception:
                pass
        _initialized.add(key)


def _bound_lock_wait(cur) -> None:
    if is_postgres():
        cur.execute("SET LOCAL lock_timeout = '10s'")


def _migration_target(stmt: str) -> Optional[tuple[str, str]]:
    """("picks", "spy_entry") for "ALTER TABLE picks ADD COLUMN spy_entry REAL", else None."""
    w = stmt.split()
    if len(w) >= 6 and [x.upper() for x in w[:2]] == ["ALTER", "TABLE"] and [x.upper() for x in w[3:5]] == ["ADD", "COLUMN"]:
        return (w[2].lower(), w[5].lower())
    return None


def _pg_columns() -> Optional[set[tuple[str, str]]]:
    """Existing (table, column) pairs in the current schema; None if the lookup fails (then migrations just run)."""
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema()")
            return {(str(t).lower(), str(c).lower()) for t, c in cur.fetchall()}
    except Exception as e:
        print(f"[db] column lookup failed ({e})")
        return None


def _migrations() -> list[str]:
    return [
        # accounts made before email verification existed count as verified
        "ALTER TABLE accounts ADD COLUMN verified INTEGER NOT NULL DEFAULT 1",
        # SPY's price at the same moment as the pick's entry price (fair baseline at any hour)
        "ALTER TABLE picks ADD COLUMN spy_entry REAL",
        # "did we express the belief well": each pick vs the simple choice (sector fund, else the
        # basket of ideas in the same direction), and whether the user's call itself came true
        "ALTER TABLE picks ADD COLUMN is_etf INTEGER",
        "ALTER TABLE outcomes ADD COLUMN bench_ret REAL",
        "ALTER TABLE outcomes ADD COLUMN sel_edge REAL",
        "ALTER TABLE outcomes ADD COLUMN belief_right INTEGER",
        "ALTER TABLE outcomes ADD COLUMN bench_kind TEXT",
        # "You called it" emails (notify.py); people can unsubscribe
        "ALTER TABLE accounts ADD COLUMN notify_calls INTEGER NOT NULL DEFAULT 1",
    ]


def reset_for_tests() -> None:
    _initialized.clear()
