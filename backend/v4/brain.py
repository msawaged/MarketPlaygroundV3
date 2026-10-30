"""
Public, aggregate view of the learning ("Watch the brain learn"). No user's own words ever appear here: the live
feeds show only beliefs the system itself practiced on (news hunches and generated beliefs) and graded picks.
Cached 60 seconds.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import db, learning, nn

_cache = {"at": 0.0, "v": None}
_lock = threading.Lock()
SEED_SOURCES = ("seed_news", "seed_live", "seed_backfill")


def _versions(limit: int = 24) -> list[dict]:
    out = []
    for r in reversed(nn.history(limit)):
        m = r.get("metrics") or {}
        out.append({
            "at": r["created_at"], "status": r["status"], "n_train": r["n_train"], "n_test": r["n_test"],
            "score": round(float(m.get("spearman") or 0), 4),                   # rank correlation on unseen beliefs
            "lift": round(float(m.get("top_pick_lift") or 0), 4),               # top pick vs the rest, unseen beliefs
            "lift_t": round(float(m.get("top_pick_lift_t") or 0), 2),
            "beliefs_in_test": m.get("beliefs_in_test"),
            "reason": m.get("reason") or "",
        })
    return out


def _growth(days: int = 30) -> list[dict]:
    """Running totals per day: beliefs learned and picks graded."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    b0 = db.query_one("SELECT COUNT(*) AS n FROM beliefs WHERE substr(created_at, 1, 10) < ?", (since.isoformat(),))
    g0 = db.query_one("SELECT COUNT(*) AS n FROM outcomes WHERE substr(graded_at, 1, 10) < ?", (since.isoformat(),))
    bd = {r["d"]: int(r["n"]) for r in db.query(
        "SELECT substr(created_at, 1, 10) AS d, COUNT(*) AS n FROM beliefs WHERE substr(created_at, 1, 10) >= ? GROUP BY d",
        (since.isoformat(),))}
    gd = {r["d"]: int(r["n"]) for r in db.query(
        "SELECT substr(graded_at, 1, 10) AS d, COUNT(*) AS n FROM outcomes WHERE substr(graded_at, 1, 10) >= ? GROUP BY d",
        (since.isoformat(),))}
    b, g = int(b0["n"] if b0 else 0), int(g0["n"] if g0 else 0)
    out = []
    for i in range(days + 1):
        d = (since + timedelta(days=i)).isoformat()
        b += bd.get(d, 0); g += gd.get(d, 0)
        out.append({"d": d, "beliefs": b, "graded": g})
    return out


def _recent_learned(limit: int = 14) -> list[dict]:
    ph = ",".join("?" for _ in SEED_SOURCES)
    rows = db.query(f"SELECT id, text, direction, created_at, source FROM beliefs WHERE source IN ({ph}) "
                    "ORDER BY created_at DESC LIMIT ?", (*SEED_SOURCES, limit))
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    picks = defaultdict(list)
    for p in db.query(f"SELECT belief_id, ticker, direction FROM picks WHERE shown = 1 AND belief_id IN ({','.join('?' for _ in ids)}) "
                      "ORDER BY final_rank", ids):
        if len(picks[p["belief_id"]]) < 3:
            picks[p["belief_id"]].append({"ticker": p["ticker"], "direction": p["direction"]})
    return [{"text": (r["text"] or "")[:120], "direction": r["direction"], "at": r["created_at"],
             "from_news": r["source"] == "seed_news", "picks": picks.get(r["id"], [])} for r in rows]


def _recent_graded(limit: int = 14) -> list[dict]:
    rows = db.query(
        """SELECT p.ticker, p.direction, o.checkpoint_days, o.dir_excess, o.graded_at
           FROM outcomes o JOIN picks p ON p.id = o.pick_id
           ORDER BY o.graded_at DESC, o.checkpoint_days DESC LIMIT ?""", (limit,))
    return [{"ticker": r["ticker"], "direction": r["direction"], "days": r["checkpoint_days"],
             "vs_market": round(float(r["dir_excess"]), 4), "right": float(r["dir_excess"]) > 0, "at": r["graded_at"]}
            for r in rows]


def _next_runs(now: datetime) -> dict:
    """When the brain next learns (hourly at :13) and next gets graded (22:47 UTC on weekdays). Matches render.yaml."""
    nxt = now.replace(minute=13, second=0, microsecond=0)
    if nxt <= now:
        nxt += timedelta(hours=1)
    g = now.replace(hour=22, minute=47, second=0, microsecond=0)
    while g <= now or g.weekday() >= 5:
        g += timedelta(days=1)
        g = g.replace(hour=22, minute=47)
    return {"learning": nxt.isoformat(), "grading": g.isoformat()}


def _activity(limit: int = 20) -> list[dict]:
    """A timeline of what happened, newest first. People appear only as the topic of their belief, never their words."""
    ev = []
    for r in db.query("SELECT themes, direction, created_at FROM beliefs WHERE source = 'user' ORDER BY created_at DESC LIMIT 10"):
        th = db.loads(r["themes"], [])
        ev.append({"kind": "person", "at": r["created_at"], "topic": th[0] if th else "", "direction": r["direction"]})
    ph = ",".join("?" for _ in SEED_SOURCES)
    for r in db.query(f"""SELECT substr(created_at, 1, 13) AS h, source, COUNT(*) AS n, MAX(created_at) AS at FROM beliefs
                          WHERE source IN ({ph}) GROUP BY substr(created_at, 1, 13), source ORDER BY h DESC LIMIT 10""", SEED_SOURCES):
        ev.append({"kind": "news" if r["source"] == "seed_news" else "practice", "at": r["at"], "n": int(r["n"])})
    for r in db.query("""SELECT substr(graded_at, 1, 13) AS h, COUNT(*) AS n, SUM(CASE WHEN dir_excess > 0 THEN 1 ELSE 0 END) AS right_n,
                         MAX(graded_at) AS at FROM outcomes GROUP BY substr(graded_at, 1, 13) ORDER BY h DESC LIMIT 6"""):
        ev.append({"kind": "graded", "at": r["at"], "n": int(r["n"]), "right": int(r["right_n"] or 0)})
    for v in nn.history(4):
        ev.append({"kind": "trained", "at": v["created_at"], "status": v["status"], "n": v["n_train"]})
    ev.sort(key=lambda e: e["at"] or "", reverse=True)
    return ev[:limit]


def health(public: bool = True) -> dict:
    """Last run of each background job. Public view: when and whether it worked, no error text."""
    out = {}
    for job in (("learning", "grading") if public else ("learning", "learning_cron", "learning_web", "grading")):
        row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (f"health:{job}",))
        h = db.loads(row["v"], None) if row else None
        if h and public:
            h = {k: h[k] for k in ("at", "ok") if k in h}
        out[job] = h
    return out


def snapshot() -> dict:
    with _lock:
        if _cache["v"] and time.time() - _cache["at"] < 15:
            return _cache["v"]
    today = datetime.now(timezone.utc).date().isoformat()
    one = lambda sql, args=(): int((db.query_one(sql, args) or {}).get("n") or 0)  # noqa: E731
    counts = {
        "beliefs": one("SELECT COUNT(*) AS n FROM beliefs"),
        "beliefs_today": one("SELECT COUNT(*) AS n FROM beliefs WHERE substr(created_at, 1, 10) = ?", (today,)),
        "from_news": one("SELECT COUNT(*) AS n FROM beliefs WHERE source = 'seed_news'"),
        "people": one("SELECT COUNT(DISTINCT user_id) AS n FROM beliefs WHERE source = 'user'"),
        "picks": one("SELECT COUNT(*) AS n FROM picks"),
        "companies": one("SELECT COUNT(DISTINCT ticker) AS n FROM picks"),
        "graded": one("SELECT COUNT(*) AS n FROM outcomes"),
        "graded_right": one("SELECT COUNT(*) AS n FROM outcomes WHERE dir_excess > 0"),
        "versions": one("SELECT COUNT(*) AS n FROM nn_models"),
        "label_days": learning.LABEL_DAYS,
    }
    themes = db.query("SELECT theme, COUNT(*) AS n FROM pick_themes GROUP BY theme ORDER BY COUNT(*) DESC LIMIT 18")
    cur = nn.status()
    v = {
        "now": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "themes": [{"theme": t["theme"], "n": int(t["n"])} for t in themes],
        "growth": _growth(),
        "versions": _versions(),
        "current": {"status": cur.get("status", "none"), "weight": round(float(cur.get("weight") or 0), 3)},
        "learned": _recent_learned(),
        "activity": _activity(),
        "health": health(public=True),
        "next": _next_runs(datetime.now(timezone.utc)),
        "graded": _recent_graded(),
    }
    with _lock:
        _cache.update(at=time.time(), v=v)
    return v
