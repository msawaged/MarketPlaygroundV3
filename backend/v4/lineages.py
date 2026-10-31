"""
Brain lineages ("survival of the smartest"): a small population of AI strategists competes on the same beliefs.

Each strategist is a different way of choosing the best company for a belief from the candidates the brain found:
Momentum likes companies already moving the right way, Value likes beaten-down ones, Steady likes calm ones,
Follow-the-AI trusts Claude's ranking, Big-picture prefers broad funds. For every graded belief, a strategist's
"call" is the candidate it ranks first, and its result is how that company did against the S&P 500 thirty days later
(practice only, no money). Once per trading day the weakest strategists are retired and the strongest evolve:
copies with slightly changed preferences. Over generations, what survives is what has worked.

Scores use the most recent graded beliefs, so the scoreboard says exactly that: how each would have done on the
latest graded calls. Selection on those same calls flatters a newborn, so a strategist only gets a say in the real
ranking (the "champion") once its LIVE record, calls graded after it was born that it never saw, beats the app's own
top pick on the same calls by a clear margin over at least LIVE_MIN calls. Cheap: no Claude calls, just arithmetic on picks the brain already graded.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from . import db

CHECKPOINT = 90          # days after the call (beliefs play out over months; 30 days is mostly noise)
WINDOW = 300             # most recent graded beliefs used for scoring
MIN_BELIEFS = 40         # don't evolve on less than this
POP_MAX = 8
CULL = 2                 # retired and replaced per generation
LIVE_MIN = 100           # live calls before a strategist can help rank real picks
LIVE_MARGIN = 0.005      # ...and it must beat the app's own top pick by half a point on average
CHAMPION_WEIGHT = 0.25   # how much a champion moves the real ranking
CHAMPION_KEY = "lineage_champion"
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
    twins = db.query_one("SELECT COUNT(*) AS n FROM strategists WHERE name LIKE ?", (name + "%",))["n"]
    if twins:  # siblings born the same generation: "Gen 5", "Gen 5b", "Gen 5c"
        name = f"{name}{chr(ord('a') + twins)}"
    db.execute("""INSERT INTO strategists (id, name, style, gen, parent_id, weights, status, born_at)
                  VALUES (?,?,?,?,?,?,?,?)""", (sid, name, style, gen, parent, db.dumps(weights), "alive", _now()))
    return sid


def _name(sid: str) -> str:
    return db.query_one("SELECT name FROM strategists WHERE id = ?", (sid,))["name"]


def ensure_founders() -> None:
    if db.query_one("SELECT COUNT(*) AS n FROM strategists")["n"]:
        return
    for style, w in FOUNDERS:
        sid = _add(f"{style} · Gen 1", style, 1, None, w)
        _event("born", sid, f"{style} · Gen 1 joined as a founder")


def _graded_beliefs(since: Optional[str] = None, limit: int = WINDOW) -> list[list[dict]]:
    """Candidates of the most recent graded beliefs: [[{feat..., ex, top}, ...], ...]. `since`: only beliefs created
    after that time (a strategist's live record: calls it never saw)."""
    rows = db.query(
        """SELECT p.belief_id, p.direction, p.features, p.final_rank, o.dir_excess, b.created_at
           FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
           WHERE o.checkpoint_days = ? AND b.created_at > ?
           ORDER BY b.created_at DESC""", (CHECKPOINT, since or ""))
    by: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        if r["belief_id"] not in by:
            if len(order) >= limit:
                continue
            by[r["belief_id"]] = []
            order.append(r["belief_id"])
        by[r["belief_id"]].append(features_of(r["features"], r["direction"], ex=float(r["dir_excess"]),
                                              top=r["final_rank"] == 1))
    return [by[b] for b in order if len(by[b]) >= 2]  # a choice needs at least two candidates


def features_of(features: object, direction: str, **extra) -> dict:
    num = (db.loads(features, {}) or {}).get("num", {}) if not isinstance(features, dict) or "num" in features else features
    sign = -1.0 if str(direction).lower() == "bearish" else 1.0
    f = {k: float(num.get(k, 0.0)) * (sign if k in DIRECTIONAL else 1.0) for k in FEATURES}
    f.update(extra)
    return f


def raw_score(weights: dict, f: dict) -> float:
    return sum(w * f.get(k, 0.0) for k, w in weights.items())


def _baseline(beliefs: list[list[dict]]) -> dict:
    """How the app's own top pick did on the same calls."""
    xs = [next((c["ex"] for c in cands if c.get("top")), None) for cands in beliefs]
    xs = [x for x in xs if x is not None]
    n = len(xs)
    return {"fitness": sum(xs) / n if n else 0.0, "beat_rate": sum(1 for x in xs if x > 0) / n if n else 0.0, "n": n}


def score(weights: dict, beliefs: list[list[dict]]) -> dict:
    results = []
    for cands in beliefs:
        best = max(cands, key=lambda c: raw_score(weights, c))
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
    """One generation: score everyone, retire the weakest, the strongest evolve."""
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
        _event("born", sid, f"{_name(sid)} evolved from {p['name']}")
        born.append(sid)
    champ = pick_champion()
    _snap["v"] = None
    return {"evolved": True, "generation": gen, "born": len(born), "retired": len(retired), "beliefs": len(beliefs),
            "champion": champ.get("name") if champ else None}


def live_record(s: dict) -> dict:
    """A strategist's record on calls created after it was born (never used to select it), next to the app's own
    top pick on the very same calls."""
    beliefs = _graded_beliefs(since=s["born_at"], limit=2000)
    return {"me": score(db.loads(s["weights"], {}), beliefs), "app": _baseline(beliefs)}


def pick_champion() -> Optional[dict]:
    """The alive strategist whose live record clearly beats the app's own top pick, if any. Stored in kv_cache."""
    best = None
    for s in db.query("SELECT * FROM strategists WHERE status = 'alive'"):
        lr = live_record(s)
        me, app = lr["me"], lr["app"]
        if me["n"] >= LIVE_MIN and me["fitness"] >= app["fitness"] + LIVE_MARGIN and me["beat_rate"] >= app["beat_rate"]:
            if not best or me["fitness"] > best["live"]["fitness"]:
                best = {"id": s["id"], "name": s["name"], "weights": db.loads(s["weights"], {}), "live": me, "app": app}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (CHAMPION_KEY,))
    if best:
        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (CHAMPION_KEY, db.dumps(best), _now()))
        _event("champion", best["id"], f"{best['name']} earned a say in ranking real picks")
    return best


def champion() -> Optional[dict]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (CHAMPION_KEY,))
    return db.loads(row["v"], None) if row else None


_snap = {"at": 0.0, "v": None}
SNAP_TTL = 600  # live records only change when calls get graded; no need to recompute every page view


def snapshot() -> dict:
    """Public view (cached 10 minutes): scoreboard, family tree, live records, recent births and retirements."""
    import time
    if _snap["v"] is not None and time.time() - _snap["at"] < SNAP_TTL:
        return _snap["v"]
    v = _snapshot()
    _snap.update(at=time.time(), v=v)
    return v


def _snapshot() -> dict:
    rows = db.query("SELECT id, name, style, gen, parent_id, status, fitness, beat_rate, n_scored, born_at FROM strategists ORDER BY gen, born_at")
    if not rows:
        return {"generation": 0, "alive": [], "tree": [], "events": [], "retired": 0}
    seen: dict[str, int] = {}
    for r in rows:  # older rows may share a name; show siblings as "Gen 2", "Gen 2b"
        k = seen.get(r["name"], 0)
        seen[r["name"]] = k + 1
        if k:
            r["name"] = f"{r['name']}{chr(ord('a') + k)}"
    names = {r["id"]: r["name"] for r in rows}
    fmt = lambda r: {"id": r["id"], "name": r["name"], "style": r["style"], "gen": r["gen"], "parent": r["parent_id"],  # noqa: E731
                     "parent_name": names.get(r["parent_id"]), "status": r["status"],
                     "fitness": round(float(r["fitness"] or 0), 4), "beat_rate": round(float(r["beat_rate"] or 0), 3),
                     "n": int(r["n_scored"] or 0), "born_at": r["born_at"]}
    tree = [fmt(r) for r in rows][-60:]
    alive = sorted([t for t in tree if t["status"] == "alive"], key=lambda t: t["fitness"], reverse=True)
    full = {r["id"]: r for r in db.query("SELECT id, born_at, weights FROM strategists WHERE status = 'alive'")}
    for a in alive:
        lr = live_record(full[a["id"]]) if a["id"] in full else {"me": {"n": 0}, "app": {"n": 0}}
        a["live"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in lr["me"].items()}
        a["live_app"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in lr["app"].items()}
    ch = champion()
    events = db.query("SELECT at, kind, detail FROM lineage_events ORDER BY at DESC LIMIT 8")
    return {"generation": max(r["gen"] for r in rows), "alive": alive, "tree": tree, "events": events,
            "retired": sum(1 for r in rows if r["status"] == "retired"), "checkpoint_days": CHECKPOINT,
            "champion": {"id": ch["id"], "name": ch["name"]} if ch else None, "live_min": LIVE_MIN}


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
