"""
Brain lineages ("survival of the smartest"): a small population of AI strategists competes on the same beliefs.

Each strategist is a different way of choosing the best company for a belief from the candidates the brain found:
Momentum likes companies already moving the right way, Value likes beaten-down ones, Steady likes calm ones,
Follow-the-AI trusts Claude's ranking, Big-picture prefers broad funds. For every graded belief, a strategist's
"call" is the candidate it ranks first, and its result is how that company did against the S&P 500 thirty days later
(practice only, no money). Once per trading day the weakest strategists are retired and the strongest have children:
copies with slightly changed preferences. Over generations, what survives is what has worked.

Scores use the most recent graded beliefs, so the scoreboard says exactly that: how each would have done on the
latest graded calls. Cheap: no Claude calls, just arithmetic on picks the brain already graded.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import db

CHECKPOINT = 30          # days after the call
WINDOW = 300             # most recent graded beliefs used for scoring
MIN_BELIEFS = 40         # don't evolve on less than this
POP_MAX = 8
CULL = 2                 # retired and replaced per generation
FEATURES = ("mom20", "mom60", "mom250", "rs60", "dist_high", "vol60", "claude_score", "claude_rank_frac", "is_etf", "same_dir")
DIRECTIONAL = {"mom20", "mom60", "mom250", "rs60", "dist_high"}  # flipped for bearish picks

FOUNDERS = [
    ("Momentum", {"mom60": 1.0, "mom20": 0.5, "rs60": 0.8}),
    ("Value", {"dist_high": -1.0, "mom250": -0.6}),
    ("Steady", {"vol60": -1.0, "claude_score": 0.3}),
    ("Follow-the-AI", {"claude_score": 1.0, "claude_rank_frac": 0.8}),
    ("Big-picture", {"is_etf": 1.0, "same_dir": 0.6}),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _event(kind: str, sid: str, detail: str) -> None:
    db.execute("INSERT INTO lineage_events (id, at, kind, strategist_id, detail) VALUES (?,?,?,?,?)",
               (f"le-{uuid.uuid4().hex[:12]}", _now(), kind, sid, detail[:200]))


def _add(name: str, style: str, gen: int, parent: Optional[str], weights: dict) -> str:
    sid = f"st-{uuid.uuid4().hex[:10]}"
    db.execute("""INSERT INTO strategists (id, name, style, gen, parent_id, weights, status, born_at)
                  VALUES (?,?,?,?,?,?,?,?)""", (sid, name, style, gen, parent, db.dumps(weights), "alive", _now()))
    return sid


def ensure_founders() -> None:
    if db.query_one("SELECT COUNT(*) AS n FROM strategists")["n"]:
        return
    for style, w in FOUNDERS:
        sid = _add(f"{style} · Gen 1", style, 1, None, w)
        _event("born", sid, f"{style} · Gen 1 joined as a founder")


def _graded_beliefs() -> list[list[dict]]:
    """Candidates of the most recent graded beliefs: [[{feat..., ex}, ...], ...]."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.nn_score, o.dir_excess, b.created_at
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ?
           ORDER BY b.created_at DESC""", (CHECKPOINT,))
    by: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        if r["belief_id"] not in by:
            if len(order) >= WINDOW:
                continue
            by[r["belief_id"]] = []
            order.append(r["belief_id"])
        num = (db.loads(r["features"], {}) or {}).get("num", {})
        sign = -1.0 if str(r["direction"]).lower() == "bearish" else 1.0
        f = {k: float(num.get(k, 0.0)) * (sign if k in DIRECTIONAL else 1.0) for k in FEATURES}
        f["ex"] = float(r["dir_excess"])
        by[r["belief_id"]].append(f)
    return [by[b] for b in order if len(by[b]) >= 2]  # a choice needs at least two candidates


def score(weights: dict, beliefs: list[list[dict]]) -> dict:
    results = []
    for cands in beliefs:
        best = max(cands, key=lambda c: sum(w * c.get(k, 0.0) for k, w in weights.items()))
        results.append(best["ex"])
    n = len(results)
    return {"fitness": sum(results) / n if n else 0.0, "beat_rate": sum(1 for x in results if x > 0) / n if n else 0.0, "n": n}


def _mutate(w: dict, rng: random.Random) -> dict:
    out = {k: v + rng.gauss(0, 0.3) for k, v in w.items()}
    if rng.random() < 0.5:  # sometimes pick up a new preference
        k = rng.choice(FEATURES)
        out[k] = out.get(k, 0.0) + rng.gauss(0, 0.5)
    return {k: round(v, 3) for k, v in out.items() if abs(v) > 0.02}


def evolve(seed: Optional[int] = None) -> dict:
    """One generation: score everyone, retire the weakest, the strongest have children."""
    ensure_founders()
    rng = random.Random(seed)
    beliefs = _graded_beliefs()
    alive = db.query("SELECT * FROM strategists WHERE status = 'alive'")
    for s in alive:
        r = score(db.loads(s["weights"], {}), beliefs)
        s.update(fitness=r["fitness"], beat_rate=r["beat_rate"], n_scored=r["n"])
        db.execute("UPDATE strategists SET fitness = ?, beat_rate = ?, n_scored = ? WHERE id = ?",
                   (r["fitness"], r["beat_rate"], r["n"], s["id"]))
    if len(beliefs) < MIN_BELIEFS:
        return {"evolved": False, "reason": f"needs {MIN_BELIEFS} graded beliefs, has {len(beliefs)}", "alive": len(alive)}
    alive.sort(key=lambda s: s["fitness"], reverse=True)
    gen = int(db.query_one("SELECT MAX(gen) AS g FROM strategists")["g"] or 1) + 1
    retired = []
    if len(alive) >= POP_MAX - 1:
        for s in alive[-CULL:]:
            db.execute("UPDATE strategists SET status = 'retired', retired_at = ? WHERE id = ?", (_now(), s["id"]))
            _event("retired", s["id"], f"{s['name']} retired after trailing the others")
            retired.append(s["id"])
        alive = alive[:-CULL]
    born = []
    parents = alive[:CULL] if alive else []
    while parents and len(alive) + len(born) < POP_MAX:
        p = parents[len(born) % len(parents)]
        child_w = _mutate(db.loads(p["weights"], {}), rng)
        r = score(child_w, beliefs)
        sid = _add(f"{p['style']} · Gen {gen}", p["style"], gen, p["id"], child_w)
        db.execute("UPDATE strategists SET fitness = ?, beat_rate = ?, n_scored = ? WHERE id = ?",
                   (r["fitness"], r["beat_rate"], r["n"], sid))
        _event("born", sid, f"{p['style']} · Gen {gen} was born from {p['name']}")
        born.append(sid)
    return {"evolved": True, "generation": gen, "born": len(born), "retired": len(retired), "beliefs": len(beliefs)}


def snapshot() -> dict:
    """Public view for the brain page: scoreboard, family tree, recent births and retirements."""
    rows = db.query("SELECT id, name, style, gen, parent_id, status, fitness, beat_rate, n_scored, born_at FROM strategists ORDER BY gen, born_at")
    if not rows:
        return {"generation": 0, "alive": [], "tree": [], "events": [], "retired": 0}
    names = {r["id"]: r["name"] for r in rows}
    fmt = lambda r: {"id": r["id"], "name": r["name"], "style": r["style"], "gen": r["gen"], "parent": r["parent_id"],  # noqa: E731
                     "parent_name": names.get(r["parent_id"]), "status": r["status"],
                     "fitness": round(float(r["fitness"] or 0), 4), "beat_rate": round(float(r["beat_rate"] or 0), 3),
                     "n": int(r["n_scored"] or 0), "born_at": r["born_at"]}
    tree = [fmt(r) for r in rows][-60:]
    alive = sorted([t for t in tree if t["status"] == "alive"], key=lambda t: t["fitness"], reverse=True)
    events = db.query("SELECT at, kind, detail FROM lineage_events ORDER BY at DESC LIMIT 8")
    return {"generation": max(r["gen"] for r in rows), "alive": alive, "tree": tree, "events": events,
            "retired": sum(1 for r in rows if r["status"] == "retired"), "checkpoint_days": CHECKPOINT}


def bootstrap_background() -> None:
    """On a fresh install, score the founders and raise the first generation so the page isn't empty until the
    next trading day's grading run. Runs once (only when there are no strategists yet)."""
    import threading
    import time

    def run():
        time.sleep(90)
        try:
            if not db.query_one("SELECT COUNT(*) AS n FROM strategists")["n"]:
                evolve()
        except Exception:
            pass

    threading.Thread(target=run, name="lineages-bootstrap", daemon=True).start()
