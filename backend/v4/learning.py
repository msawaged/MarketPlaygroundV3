"""
Shared learning context, computed from ALL users' graded beliefs.

- similar_beliefs(): past beliefs that read like the new one, with how their
  picks were graded. Fed to Claude so its suggestions improve over time.
- ticker_stats(): per theme, which tickers have actually expressed it well.
  Also used as a score adjustment (shrunk toward zero until there's data).
- structure_stats(): which trade structures have worked for a direction and
  horizon — lets the strategy rules shift when the evidence is clear.

"Directional excess" = how much the ticker beat SPY in the direction the
belief called for (a bearish pick that fell 10% while SPY rose 2% = +12%).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from . import db
from .strategy import horizon_bucket

LABEL_DAYS = int(os.getenv("MP_LABEL_DAYS", "30"))
_SIM_TTL = 600
_sim_lock = threading.Lock()
_sim_cache: dict = {"at": 0.0, "vec": None, "mat": None, "rows": []}


def _fmt(x: Optional[float]) -> str:
    return "ungraded" if x is None else f"{x:+.1%}"


def _load_similarity_index():
    with _sim_lock:
        if _sim_cache["vec"] is not None and time.time() - _sim_cache["at"] < _SIM_TTL:
            return _sim_cache
        rows = db.query(
            """SELECT b.id, b.text, b.themes FROM beliefs b
               WHERE EXISTS (SELECT 1 FROM picks p JOIN outcomes o ON o.pick_id = p.id WHERE p.belief_id = b.id)
               ORDER BY b.created_at DESC LIMIT 20000"""
        )
        if len(rows) < 3:
            _sim_cache.update(at=time.time(), vec=None, mat=None, rows=[])
            return _sim_cache
        from sklearn.feature_extraction.text import TfidfVectorizer

        docs = [f"{r['text']} {' '.join(db.loads(r['themes'], []))}" for r in rows]
        vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True, stop_words="english")
        mat = vec.fit_transform(docs)
        _sim_cache.update(at=time.time(), vec=vec, mat=mat, rows=rows)
        return _sim_cache


def invalidate() -> None:
    with _sim_lock:
        _sim_cache.update(at=0.0, vec=None, mat=None, rows=[])


def similar_beliefs(text: str, k: int = 6, min_sim: float = 0.12) -> list[dict]:
    idx = _load_similarity_index()
    if idx["vec"] is None:
        return []
    q = idx["vec"].transform([text])
    sims = (idx["mat"] @ q.T).toarray().ravel()
    order = sims.argsort()[::-1][:k]
    out = []
    for i in order:
        if sims[i] < min_sim:
            break
        r = idx["rows"][i]
        picks = db.query(
            """SELECT p.ticker, p.direction,
                      (SELECT o.dir_excess FROM outcomes o WHERE o.pick_id = p.id
                        ORDER BY o.checkpoint_days DESC LIMIT 1) AS result
               FROM picks p WHERE p.belief_id = ? ORDER BY p.final_rank LIMIT 5""",
            (r["id"],),
        )
        out.append({
            "text": r["text"],
            "themes": db.loads(r["themes"], []),
            "similarity": round(float(sims[i]), 3),
            "picks": [{"ticker": p["ticker"], "result": _fmt(p["result"])} for p in picks],
        })
    return out


def ticker_stats(themes: list[str], tickers: Optional[list[str]] = None, limit: int = 10) -> list[dict]:
    """Aggregate graded results per ticker for picks tagged with any of `themes`."""
    if not themes:
        return []
    ph = ",".join("?" for _ in themes)
    params: list = [LABEL_DAYS, *themes]
    tick_sql = ""
    if tickers:
        tick_sql = f" AND p.ticker IN ({','.join('?' for _ in tickers)})"
        params += list(tickers)
    rows = db.query(
        f"""SELECT p.ticker,
                   COUNT(DISTINCT p.id) AS n,
                   AVG(o.dir_excess) AS mean,
                   AVG(CASE WHEN p.direction = 'bearish' THEN -o.dir_excess ELSE o.dir_excess END) AS raw_mean,
                   AVG(CASE WHEN o.dir_excess > 0 THEN 1.0 ELSE 0.0 END) AS hit
            FROM picks p
            JOIN outcomes o ON o.pick_id = p.id AND o.checkpoint_days = ?
            WHERE p.id IN (SELECT pick_id FROM pick_themes WHERE theme IN ({ph})){tick_sql}
            GROUP BY p.ticker
            ORDER BY COUNT(DISTINCT p.id) DESC
            LIMIT {int(limit) if not tickers else 1000}""",
        params,
    )
    fb = feedback_counts([r["ticker"] for r in rows])
    for r in rows:
        r["mean"] = float(r["mean"] or 0.0)          # how picks did in the direction they called
        r["raw_mean"] = float(r["raw_mean"] or 0.0)  # how the stock itself did vs SPY
        r["hit"] = float(r["hit"] or 0.0)
        r["n"] = int(r["n"])
        r.update(fb.get(r["ticker"], {"up": 0, "down": 0}))
    return rows


def feedback_counts(tickers: list[str]) -> dict[str, dict]:
    if not tickers:
        return {}
    ph = ",".join("?" for _ in tickers)
    rows = db.query(
        f"""SELECT p.ticker,
                   SUM(CASE WHEN f.kind IN ('up','executed') THEN 1 ELSE 0 END) AS up,
                   SUM(CASE WHEN f.kind = 'down' THEN 1 ELSE 0 END) AS down
            FROM feedback f JOIN picks p ON p.id = f.pick_id
            WHERE p.ticker IN ({ph}) GROUP BY p.ticker""",
        tickers,
    )
    return {r["ticker"]: {"up": int(r["up"] or 0), "down": int(r["down"] or 0)} for r in rows}


def ticker_adjustment(stat: Optional[dict], direction: str = "bullish", prior_n: int = 20) -> float:
    """Shrunk score nudge in [-0.25, 0.25] from graded history + user votes.

    Uses how the stock itself did vs SPY, pointed in THIS pick's direction. (Averaging
    past bullish and bearish picks together rewarded stocks that rose even when the new
    pick was a bet against them; the offline check in ml_check.py caught this.)"""
    if not stat:
        return 0.0
    n = stat.get("n", 0)
    sign = -1.0 if direction == "bearish" else 1.0
    raw = stat.get("raw_mean", stat.get("mean", 0.0))
    market = (n / (n + prior_n)) * max(-0.15, min(0.15, sign * raw)) * 1.5
    up, down = stat.get("up", 0), stat.get("down", 0)
    votes = (up - down) / (up + down + 10)
    return max(-0.25, min(0.25, market + 0.05 * votes))


def structure_stats(direction: str, horizon_days: int) -> dict:
    bucket = horizon_bucket(horizon_days)
    lo, hi = {"short": (0, 45), "medium": (46, 180), "long": (181, 100000)}[bucket]
    rows = db.query(
        """SELECT p.structure, COUNT(*) AS n, AVG(o.structure_ret) AS mean
           FROM picks p
           JOIN beliefs b ON b.id = p.belief_id
           JOIN outcomes o ON o.pick_id = p.id AND o.checkpoint_days = ?
           WHERE p.direction = ? AND b.horizon_days BETWEEN ? AND ?
             AND o.structure_ret IS NOT NULL AND p.structure IS NOT NULL
           GROUP BY p.structure""",
        (LABEL_DAYS, direction, lo, hi),
    )
    return {r["structure"]: {"n": int(r["n"]), "mean": float(r["mean"] or 0.0)} for r in rows}


def build_context(text: str) -> dict:
    sims = similar_beliefs(text)
    themes: list[str] = []
    for s in sims:
        for t in s["themes"]:
            if t not in themes:
                themes.append(t)
    return {"similar": sims, "ticker_stats": ticker_stats(themes[:8], limit=8)}
