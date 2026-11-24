"""
"Put it on your home screen" (2026-11-24, feature_ideas.md 2026-11-23): how many people are offered the home-screen
app, add it, say not now, and open it from the home screen.

Counts only: one row per (day, kind) in install_counts, no device or account stored. Each device counts once per kind
per day (in-memory, so a busy device can't inflate a number), and each kind has a daily cap so a script can't either.
The counts show on Agent HQ (owner only) as the last 7 days.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import db

KINDS = ("shown", "accepted", "dismissed", "installed", "opened_standalone")
DAILY_CAP = 2000          # per kind per day; far above real traffic (7 real users since Oct 1)
_SEEN_MAX = 20000         # in-memory dedupe set is cleared past this size (and every new day)

_lock = threading.Lock()
_seen: set = set()
_seen_day: Optional[str] = None


def init() -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS install_counts (
        day TEXT NOT NULL,
        kind TEXT NOT NULL,
        n INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (day, kind)
    )""")


def _today(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).date().isoformat()


def record(kind: str, device_id: Optional[str] = None, now: Optional[datetime] = None) -> dict:
    """Count one event. Unknown kinds are refused; repeats from the same device on the same day are ignored."""
    global _seen_day
    kind = str(kind or "").strip()
    if kind not in KINDS:
        raise ValueError("Unknown event.")
    init()
    day = _today(now)
    dev = str(device_id or "").strip()[:80]
    with _lock:
        if _seen_day != day or len(_seen) > _SEEN_MAX:
            _seen.clear()
            _seen_day = day
        if dev:
            key = (dev, kind)
            if key in _seen:
                return {"ok": True, "counted": False}
            _seen.add(key)
    row = db.query_one("SELECT n FROM install_counts WHERE day = ? AND kind = ?", (day, kind))
    if row and int(row["n"]) >= DAILY_CAP:
        return {"ok": True, "counted": False}
    if not db.execute("UPDATE install_counts SET n = n + 1 WHERE day = ? AND kind = ?", (day, kind)):
        try:
            db.execute("INSERT INTO install_counts (day, kind, n) VALUES (?, ?, 1)", (day, kind))
        except Exception:   # another worker inserted the same row first
            db.execute("UPDATE install_counts SET n = n + 1 WHERE day = ? AND kind = ?", (day, kind))
    return {"ok": True, "counted": True}


def week(now: Optional[datetime] = None, days: int = 7) -> dict:
    """Totals per kind over the last `days` days, today included."""
    init()
    start = ((now or datetime.now(timezone.utc)) - timedelta(days=days - 1)).date().isoformat()
    rows = db.query("SELECT kind, SUM(n) AS n FROM install_counts WHERE day >= ? GROUP BY kind", (start,))
    out = {k: 0 for k in KINDS}
    for r in rows:
        if r["kind"] in out:
            out[r["kind"]] = int(r["n"] or 0)
    out["days"] = days
    return out
