"""
v4 belief engine — the flow for every belief, from any user or the seeder:

  1. Pull what the system has learned from all users (similar beliefs, ticker
     track records).
  2. ONE Claude call: interpret the belief, propose candidate tickers.
  3. Validate every candidate against Alpaca (real, tradable, has prices).
  4. Score: Claude's score + graded track record + neural network (when it
     has earned a say).
  5. Rules pick the trade structure; graded results can shift the rules.
  6. Save everything so it can be graded and learned from.

Returns the same response shape the existing frontend reads, plus a `picks`
list with the alternatives.
"""
from __future__ import annotations

import os
import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from . import db, interpreter, learning, market, nn, strategy

SHOW_TOP = 3
CACHE_HOURS = 6


class BeliefError(ValueError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$%.\s]", " ", text.lower())).strip()


class BudgetError(BeliefError):
    """Today's cap on Claude calls was reached (protects the bill from scripts and runaway use)."""


def _bump(key: str) -> int:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (key,))
    n = int(row["v"]) + 1 if row and str(row["v"]).isdigit() else 1
    db.execute("DELETE FROM kv_cache WHERE k = ?", (key,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (key, str(n), datetime.now(timezone.utc).isoformat()))
    return n


def _spend_guard(user_id: str) -> None:
    """Caps on fresh Claude calls from people (cached repeats and the practice feed don't count):
    MP_DAILY_CLAUDE_CAP for everyone together per day (default 1500, roughly a few dollars),
    MP_USER_DAILY_CAP per person per day (default 60)."""
    day = market.today().isoformat()
    cap_all = int(os.getenv("MP_DAILY_CLAUDE_CAP", "1500"))
    cap_user = int(os.getenv("MP_USER_DAILY_CAP", "60"))
    total = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (f"claude_calls:{day}",))
    if cap_all > 0 and total and str(total["v"]).isdigit() and int(total["v"]) >= cap_all:
        raise BudgetError("MarketPlayground is very busy today and hit its beta limit. Please try again tomorrow.")
    if cap_user > 0 and user_id and user_id != "anonymous":
        mine = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (f"claude_calls:{day}:{user_id}",))
        if mine and str(mine["v"]).isdigit() and int(mine["v"]) >= cap_user:
            raise BudgetError("You've explored a lot of ideas today! Fresh ideas reset tomorrow; repeats still work.")
        _bump(f"claude_calls:{day}:{user_id}")
    _bump(f"claude_calls:{day}")


def _cached_interpretation(norm: str, risk: str) -> Optional[tuple[dict, dict]]:
    key = hashlib.sha1(f"{norm}|{risk}".encode()).hexdigest()  # risk carries the prefs too (see process_belief)
    row = db.query_one("SELECT v, created_at FROM kv_cache WHERE k = ?", (key,))
    if not row:
        return None
    if datetime.fromisoformat(row["created_at"]) < datetime.now(timezone.utc) - timedelta(hours=CACHE_HOURS):
        return None
    v = db.loads(row["v"])
    return v["interp"], {**v["usage"], "cost_usd": 0.0, "cached": True}


def _store_interpretation(norm: str, risk: str, interp: dict, usage: dict) -> None:
    key = hashlib.sha1(f"{norm}|{risk}".encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    db.execute("DELETE FROM kv_cache WHERE k = ?", (key,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
               (key, db.dumps({"interp": interp, "usage": usage}), now))


def process_belief(
    belief: str,
    user_id: str = "anonymous",
    risk_profile: str = "moderate",
    *,
    as_of: Optional[date] = None,
    source: str = "user",
    model: Optional[str] = None,
    claude_client: Any = None,
    prefs: Optional[dict] = None,
) -> dict:
    belief = (belief or "").strip()
    if not belief:
        raise BeliefError("Belief is required")
    if len(belief) > 1000:
        raise BeliefError("Belief is too long (max 1000 characters)")
    risk_profile = (risk_profile or "moderate").lower()
    if risk_profile not in ("conservative", "moderate", "aggressive"):
        risk_profile = "moderate"
    backfill = as_of is not None and as_of < market.today()
    as_of = as_of or market.today()
    norm = _norm(belief)

    # 1-2. learned context + one Claude call (live requests reuse a recent identical interpretation)
    prefs = strategy.normalize_prefs(prefs)
    cache_key = f"p2|{risk_profile}|{prefs['instrument']}|{prefs['goal']}"  # p2: direction-first prompt
    cached = None if backfill else _cached_interpretation(norm, cache_key)
    if cached:
        interp, usage = cached
    else:
        if source == "user":
            _spend_guard(user_id)
        context = learning.build_context(belief)
        interp, usage = interpreter.interpret(
            belief, risk_profile, as_of=as_of if backfill else None,
            context=context, model=model, client=claude_client, prefs=prefs,
        )
        if not backfill:
            _store_interpretation(norm, cache_key, interp, usage)

    belief_id = f"b-{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "belief_id": belief_id, "user_id": user_id, "risk_profile": risk_profile,
        "interpretation": {k: interp.get(k) for k in ("summary", "causal_chain", "themes", "horizon_days", "conviction", "direction",
                                                      "wrong_if", "exit_rule", "clarify_question", "clarify_options")},
        "engine": "v4", "usage": usage, "prefs": prefs,
    }

    if not interp.get("is_market_belief") or not interp.get("candidates"):
        return {**base, "strategy": None, "picks": [], "valid": False,
                "error": "not_a_market_belief",
                "reason": interp.get("note") or "I couldn't find a market angle in that. Try describing what you think will grow, shrink, or change."}

    # 3. validate candidates
    # SPY is priced at the same moment as the picks so the "vs the market" grade compares like with like,
    # whatever hour the belief comes in (before the open, after the close, weekends).
    spy_entry: Optional[float] = None
    if not backfill:
        try:
            spy_entry = float(market.latest_price("SPY"))
        except Exception:
            spy_entry = None
    cands = interp["candidates"]
    valid: list[dict] = []
    for rank, c in enumerate(cands):
        try:
            info = market.asset_info(c["ticker"])
            if not info:
                continue
            entry_date, price = market.price_on(c["ticker"], as_of if backfill else None)
            feats = market.features(c["ticker"], as_of)
        except market.MarketDataError:
            continue
        valid.append({**c, "rank": rank, "info": info, "entry_date": entry_date, "price": price, "mkt": feats})
    if not valid:
        return {**base, "strategy": None, "picks": [], "valid": False, "error": "no_tradable_tickers",
                "reason": "None of the suggested tickers could be verified as tradable right now. Try rephrasing the belief."}

    # 4. score
    records = [
        nn.make_features(
            belief_text=belief, themes=interp["themes"], core_direction=interp["direction"],
            horizon_days=interp["horizon_days"], conviction=interp["conviction"], cand=v,
            market=v["mkt"], rank=v["rank"], n_cands=len(cands), is_etf=v["info"]["is_etf"], backfill=backfill,
        )
        for v in valid
    ]
    preds, w, model_id = nn.predict(records)
    stats = {s["ticker"]: s for s in learning.ticker_stats(interp["themes"], [v["ticker"] for v in valid])}
    claude_parts = [v["score"] + learning.ticker_adjustment(stats.get(v["ticker"]), v.get("direction", "bullish")) for v in valid]
    # what people see: track records from real people's beliefs only (never the practice feed)
    shown_stats = {s["ticker"]: s for s in learning.ticker_stats(interp["themes"], [v["ticker"] for v in valid], real_only=True)}
    nn_parts = nn.on_claude_scale(preds, claude_parts) if preds else claude_parts
    for i, v in enumerate(valid):
        v["features"] = records[i]
        v["nn_score"] = preds[i] if preds else None
        v["final_score"] = (1 - w) * claude_parts[i] + w * nn_parts[i]
        v["track"] = shown_stats.get(v["ticker"])
    # The user's stated direction always leads: on a bearish belief, bets against the companies it hurts
    # come first, and opposite-direction ideas (e.g. a competitor that benefits) can only follow them.
    # Scores still order picks within each group. (Without this, a network trained mostly in a rising
    # market learned "bullish picks score higher" and floated beneficiaries above the user's actual call.)
    core = interp["direction"]
    def _leads(v):
        return 1 if core not in ("bullish", "bearish") or v.get("direction") == core else 0
    valid.sort(key=lambda v: (_leads(v), v["final_score"]), reverse=True)

    # 5. structures
    picks_out = []
    rows_picks, rows_themes = [], []
    for final_rank, v in enumerate(valid):
        sstats = learning.structure_stats(v["direction"], interp["horizon_days"])
        tp = float(interp.get("target_price") or 0) if final_rank == 0 else 0.0
        structure, why = strategy.select(
            v["direction"], interp["horizon_days"], interp["conviction"], risk_profile, prefs,
            claude_pick=v.get("strategy", ""), claude_why=v.get("strategy_why", ""), stats=sstats, rank=final_rank,
            is_etf=bool(v["info"].get("is_etf")), price=float(v["price"]), target_price=tp,
        )
        trade = strategy.build_trade(structure, v["ticker"], v["price"], v["mkt"]["vol60"], date.fromisoformat(v["entry_date"]),
                                     interp["horizon_days"], target_price=tp if structure == "Long Call Butterfly" else 0.0)
        pick_id = f"p-{uuid.uuid4().hex[:16]}"
        shown = final_rank < SHOW_TOP
        pick = {
            "pick_id": pick_id, "ticker": v["ticker"], "name": v["info"]["name"] or v.get("name"),
            "direction": v["direction"], "exposure": v["exposure"], "rationale": v["rationale"],
            "price": round(v["price"], 2), "entry_date": v["entry_date"],
            "structure": structure, "structure_reason": why, "trade": trade,
            "score": round(v["final_score"], 4), "claude_score": v["score"],
            "nn_score": None if v["nn_score"] is None else round(v["nn_score"], 4),
            "track_record": v["track"], "shown": shown,
        }
        picks_out.append(pick)
        rows_picks.append((
            pick_id, belief_id, v["ticker"], pick["name"], v["exposure"], v["direction"], v["rationale"],
            v["rank"], v["score"], v["nn_score"], v["final_score"], final_rank, 1 if shown else 0,
            v["entry_date"], v["price"], structure, db.dumps(trade), db.dumps(v["features"]), spy_entry,
            1 if v["info"].get("is_etf") else 0,
        ))
        rows_themes += [(pick_id, t) for t in interp["themes"]]

    # 6. persist
    db.execute(
        """INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, risk_profile,
                                direction, horizon_days, conviction, themes, interpretation, model, cost_usd)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (belief_id, user_id, belief, norm, now, as_of.isoformat(), source, risk_profile, interp["direction"],
         interp["horizon_days"], interp["conviction"], db.dumps(interp["themes"]), db.dumps(interp),
         usage.get("model"), usage.get("cost_usd", 0.0)),
    )
    db.executemany(
        """INSERT INTO picks (id, belief_id, ticker, name, exposure, direction, rationale, claude_rank, claude_score,
                              nn_score, final_score, final_rank, shown, entry_date, entry_price, structure, legs, features, spy_entry, is_etf)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows_picks,
    )
    db.executemany("INSERT INTO pick_themes (pick_id, theme) VALUES (?,?)", rows_themes)

    return _legacy_shape(base, interp, picks_out, model_id, w)


def _legacy_shape(base: dict, interp: dict, picks: list[dict], model_id: Optional[str], w: float) -> dict:
    """Top pick in the fields the existing ChatInterface reads, plus all picks."""
    top = picks[0]
    trade = top["trade"]
    is_option = any(l.get("instrument") == "option" for l in trade["trade_legs"])
    others = [p["ticker"] for p in picks[1:SHOW_TOP]]
    explanation = f"{interp['causal_chain']} {top['ticker']}: {top['rationale']}"
    if others:
        explanation += f" Also consider: {', '.join(others)}."
    if trade.get("estimated"):
        explanation += " Option prices are estimates — check the live quote before trading."
    first_opt = next((l for l in trade["trade_legs"] if l.get("instrument") == "option"), {})
    return {
        **base,
        "pick_id": top["pick_id"],
        "strategy": {
            "type": trade["type"],
            "description": f"{trade['type']} on {top['ticker']}",
            "trade_legs": trade["trade_legs"],
            "expiration": trade.get("expiration"),
            "explanation": explanation,
            "source": "claude+nn" if w > 0 else "claude",
            "structure_reason": top["structure_reason"],
            "ticker": top["ticker"],
        },
        "ticker": top["ticker"],
        "asset_class": "options" if is_option else ("etf" if top["exposure"] == "etf" else "equity"),
        "tags": interp["themes"],
        "direction": top["direction"],
        "price_info": {"latest": top["price"]},
        "confidence": round(max(0.05, min(0.99, top["score"])), 2),
        "timeframe": f"{interp['horizon_days']} days",
        "goal_type": "express_belief",
        "expiry_date": trade.get("expiration") or "N/A",
        "explanation": explanation,
        "strike_price": first_opt.get("strike_price"),
        "premium": first_opt.get("est_premium"),
        "break_even": trade.get("break_even"),
        "max_profit": trade.get("max_profit"),
        "max_loss": trade.get("max_loss"),
        "valid": True,
        "picks": picks,
        "nn": {"model_id": model_id, "weight": round(w, 3)},
    }


def record_feedback(belief_id: str, kind: str, user_id: str = "anonymous", pick_id: Optional[str] = None) -> dict:
    kind = kind.lower()
    if kind in ("good", "like", "thumbs_up"):
        kind = "up"
    if kind in ("bad", "dislike", "thumbs_down"):
        kind = "down"
    if kind not in ("up", "down", "executed"):
        raise BeliefError("kind must be up, down or executed")
    if not db.query_one("SELECT id FROM beliefs WHERE id = ?", (belief_id,)):
        raise BeliefError("unknown belief_id")
    if pick_id is None:
        top = db.query_one("SELECT id FROM picks WHERE belief_id = ? ORDER BY final_rank LIMIT 1", (belief_id,))
        pick_id = top["id"] if top else None
    fid = f"f-{uuid.uuid4().hex[:16]}"
    db.execute(
        "INSERT INTO feedback (id, belief_id, pick_id, user_id, kind, created_at) VALUES (?,?,?,?,?,?)",
        (fid, belief_id, pick_id, user_id, kind, datetime.now(timezone.utc).isoformat()),
    )
    return {"status": "ok", "feedback_id": fid}


def get_belief(belief_id: str) -> Optional[dict]:
    b = db.query_one("SELECT * FROM beliefs WHERE id = ?", (belief_id,))
    if not b:
        return None
    b["themes"] = db.loads(b["themes"], [])
    b["interpretation"] = db.loads(b["interpretation"], {})
    picks = db.query("SELECT * FROM picks WHERE belief_id = ? ORDER BY final_rank", (belief_id,))
    for p in picks:
        p["legs"] = db.loads(p["legs"], {})
        p.pop("features", None)
        p["outcomes"] = db.query(
            "SELECT checkpoint_days, eval_date, ret, spy_ret, dir_excess, structure_ret FROM outcomes WHERE pick_id = ? ORDER BY checkpoint_days",
            (p["id"],),
        )
    b["picks"] = picks
    return b


def stats() -> dict:
    by_source = db.query("SELECT source, COUNT(*) AS n, SUM(cost_usd) AS cost FROM beliefs GROUP BY source")
    graded = db.query_one(
        "SELECT COUNT(DISTINCT pick_id) AS n FROM outcomes WHERE checkpoint_days = ?", (learning.LABEL_DAYS,)
    )
    users = db.query_one("SELECT COUNT(DISTINCT user_id) AS n FROM beliefs WHERE source = 'user'")
    return {
        "beliefs": {r["source"]: {"count": int(r["n"]), "claude_cost_usd": round(float(r["cost"] or 0), 4)} for r in by_source},
        "users": int(users["n"] if users else 0),
        "graded_picks": int(graded["n"] if graded else 0),
        "label_days": learning.LABEL_DAYS,
        "network": nn.status(),
    }


def trending(days: int = 14, limit: int = 8) -> dict:
    """
    What people believe right now, across all users: top themes with how many
    beliefs mention them, the usual direction, a sample view (Claude's one-line
    summary, never a user's own words), and the tickers most picked for it with
    their graded track record.
    """
    from collections import Counter, defaultdict

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.query(
        "SELECT id, themes, direction, interpretation, source FROM beliefs "
        "WHERE created_at >= ? AND source = 'user' ORDER BY created_at DESC LIMIT 5000",
        (cutoff,),
    )
    window = f"last {days} days"
    if len(rows) < 5:  # quiet period: fall back to all recent history
        rows = db.query(
            "SELECT id, themes, direction, interpretation, source FROM beliefs "
            "WHERE source = 'user' ORDER BY created_at DESC LIMIT 5000"
        )
        window = "all time"
    counts: Counter = Counter()
    dirs: dict = defaultdict(Counter)
    examples: dict = {}
    ids_by_theme: dict = defaultdict(list)
    for r in rows:
        interp = db.loads(r["interpretation"], {})
        for t in db.loads(r["themes"], [])[:3]:
            counts[t] += 1
            dirs[t][r["direction"] or "neutral"] += 1
            ids_by_theme[t].append(r["id"])
            if t not in examples and interp.get("summary"):
                examples[t] = interp["summary"]
    out = []
    for theme, n in counts.most_common(limit):
        ids = ids_by_theme[theme][:500]
        ph = ",".join("?" for _ in ids)
        top = db.query(
            f"SELECT ticker, COUNT(*) AS n FROM picks WHERE belief_id IN ({ph}) AND shown = 1 "
            f"GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT 3",
            ids,
        )
        stats = {s["ticker"]: s for s in learning.ticker_stats([theme], [t["ticker"] for t in top], real_only=True)} if top else {}
        out.append({
            "theme": theme,
            "beliefs": n,
            "direction": dirs[theme].most_common(1)[0][0],
            "example": examples.get(theme, ""),
            "tickers": [
                {"ticker": t["ticker"], "picked": int(t["n"]),
                 "graded": (stats.get(t["ticker"]) or {}).get("n", 0),
                 "avg_vs_spy": (stats.get(t["ticker"]) or {}).get("mean"),
                 "hit_rate": (stats.get(t["ticker"]) or {}).get("hit")}
                for t in top
            ],
        })
    return {"window": window, "themes": out}


# ---------------- what users see about learning and their own calls ----------------

def expression_scorecard(checkpoint: int = 30, real_only: bool = False) -> dict:
    """The two questions, kept apart:
    calls  — how often the beliefs themselves came true (the user's part)
    picks  — how the shown picks did vs the simple way to trade the same idea (our part)"""
    real = " AND b.source = 'user'" if real_only else ""
    calls = db.query_one(
        f"""SELECT COUNT(*) AS n, AVG(r) AS rate FROM (
                SELECT p.belief_id, MAX(o.belief_right) AS r
                FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
                WHERE o.checkpoint_days = ? AND o.belief_right IS NOT NULL{real}
                GROUP BY p.belief_id) x""", (checkpoint,)) or {}

    def picks(extra: str = "") -> dict:
        r = db.query_one(
            f"""SELECT COUNT(*) AS n, AVG(o.sel_edge) AS edge,
                       AVG(CASE WHEN o.sel_edge > 0 THEN 1.0 ELSE 0.0 END) AS beat
                FROM outcomes o JOIN picks p ON p.id = o.pick_id JOIN beliefs b ON b.id = p.belief_id
                WHERE o.checkpoint_days = ? AND o.sel_edge IS NOT NULL AND p.shown = 1{real}{extra}""",
            (checkpoint,)) or {}
        return {"n": int(r.get("n") or 0), "avg_edge": round(float(r.get("edge") or 0.0), 4),
                "beat_rate": round(float(r.get("beat") or 0.0), 3)}

    return {
        "checkpoint_days": checkpoint,
        "calls": {"n": int(calls.get("n") or 0), "came_true_rate": round(float(calls.get("rate") or 0.0), 3)},
        "picks": picks(),
        "picks_when_right": picks(" AND o.belief_right = 1"),
        "top_pick": picks(" AND p.final_rank = 0"),
    }


def learning_status() -> dict:
    """Plain-English, aggregate-only view of how the shared learning is going (public)."""
    st = stats()
    seeds = sum(v["count"] for k, v in st["beliefs"].items() if k.startswith("seed"))
    users_beliefs = st["beliefs"].get("user", {}).get("count", 0)
    graded = st["graded_picks"]
    net = st["network"]
    m = net.get("metrics") or {}
    if net.get("status") == "active":
        net_line = (f"It earned a {int(round(net.get('weight', 0) * 100))}% say in ranking by improving "
                    "picks on later beliefs it had never seen.")
    elif net.get("status") == "shadow":
        net_line = f"Practicing in the background. Not changing your picks yet: {m.get('reason', 'still learning')}."
    else:
        need = nn.MIN_TRAIN + nn.MIN_TEST
        net_line = f"Waiting for data. Starts training after {need} graded picks ({graded} so far)."
    track_on = graded >= 20
    versions = []
    for h in reversed(nn.history(12)):
        hm = h["metrics"] or {}
        versions.append({
            "date": (h["created_at"] or "")[:10], "status": h["status"], "examples": h["n_train"],
            "accuracy": round(float(hm.get("spearman", 0.0)), 3),
            "gain_vs_claude": round(float(hm.get("blend_gain_vs_claude", 0.0)), 4),
        })
    return {
        "beliefs_from_people": users_beliefs,
        "people": st["users"],
        "practice_beliefs": seeds,
        "graded_picks": graded,
        "label_days": st["label_days"],
        "layers": [
            {"name": "Claude", "on": True,
             "what": "Reads your belief and finds the companies and funds it affects."},
            {"name": "Track record", "on": track_on,
             "what": ("Nudges picks up or down based on how similar picks actually did." if track_on
                      else "Turns on once enough picks have been graded.")},
            {"name": "MarketPlayground network", "on": net.get("status") == "active", "status": net.get("status", "none"),
             "what": net_line + " It's judged on one thing: picking companies and trades that express each belief "
                                "better than the simple choice (the sector fund). Whether a belief comes true is up to the person."},
        ],
        "versions": versions,
        "scorecard": expression_scorecard(30),
        "scorecard_real": expression_scorecard(30, real_only=True),
        "network_target": nn.TARGET,
    }


_live_cache: dict = {}


def _live_price(symbol: str) -> Optional[float]:
    """Latest trade, cached 60s per symbol (My calls shows many picks at once)."""
    import time as _t
    hit = _live_cache.get(symbol)
    if hit and _t.time() - hit[0] < 60:
        return hit[1]
    try:
        v = float(market.latest_price(symbol))
    except Exception:
        return None
    _live_cache[symbol] = (_t.time(), v)
    return v


def _close_on(symbol: str, d: str) -> Optional[float]:
    try:
        dates, closes = market.daily_closes(symbol)
    except Exception:
        return None
    import bisect
    i = bisect.bisect_right(dates, d) - 1
    return closes[i] if i >= 0 else None


def my_beliefs(user_id: str, limit: int = 30) -> dict:
    """A user's own beliefs with how the picks they were shown are doing so far."""
    if not user_id or user_id == "anonymous":
        return {"beliefs": [], "summary": None}
    rows = db.query(
        "SELECT id, text, created_at, as_of_date, direction, horizon_days, interpretation FROM beliefs "
        "WHERE user_id = ? AND source = 'user' ORDER BY created_at DESC LIMIT ?",
        (user_id, int(limit)),
    )
    if not rows:
        return {"beliefs": [], "summary": None}
    ids = [r["id"] for r in rows]
    ph = ",".join("?" for _ in ids)
    # shown picks, plus any sector fund among the ideas (the "simple choice" each pick is compared with)
    picks = db.query(
        f"SELECT id, belief_id, ticker, name, direction, entry_date, entry_price, structure, final_rank, spy_entry, shown, is_etf "
        f"FROM picks WHERE (shown = 1 OR is_etf = 1) AND belief_id IN ({ph}) ORDER BY final_rank",
        ids,
    )
    today_s = market.today().isoformat()
    spy_now = _live_price("SPY") or _close_on("SPY", today_s)
    by_belief: dict = {}
    for p in picks:
        now = _live_price(p["ticker"]) or _close_on(p["ticker"], today_s)
        spy0 = p.get("spy_entry") or _close_on("SPY", p["entry_date"])
        p["ret"] = (now / float(p["entry_price"]) - 1) if now and p["entry_price"] else None
        p["spy_r"] = (spy_now / spy0 - 1) if spy_now and spy0 else None
        p["now"] = now
        by_belief.setdefault(p["belief_id"], []).append(p)

    def _signed(direction: str, x: float) -> float:
        return -x if direction == "bearish" else x

    out = []
    calls_tracked = calls_right = ahead = tracked = 0
    for r in rows:
        interp = db.loads(r["interpretation"], {}) or {}
        ps = [p for p in by_belief.get(r["id"], []) if p["ret"] is not None]
        # the simple choice per direction: the sector fund if there is one, else the average of the shown picks
        bench: dict = {}
        for d in {p["direction"] for p in ps}:
            g = [p for p in ps if p["direction"] == d]
            funds = [p for p in g if p.get("is_etf")]
            if funds:
                bench[d] = (sum(p["ret"] for p in funds) / len(funds), funds[0]["ticker"], {p["id"] for p in funds})
            elif len([p for p in g if p["shown"]]) > 1:
                sg = [p for p in g if p["shown"]]
                bench[d] = (sum(p["ret"] for p in sg) / len(sg), None, set())
        items = []
        for p in by_belief.get(r["id"], []):
            if not p["shown"]:
                continue
            item = {"pick_id": p["id"], "ticker": p["ticker"], "name": p["name"], "direction": p["direction"],
                    "structure": p["structure"], "entry_date": p["entry_date"], "entry_price": p["entry_price"],
                    "price_now": p["now"], "return": None, "vs_spy": None, "vs_simple": None, "simple": None}
            if p["ret"] is not None:
                item["return"] = round(p["ret"], 4)
                if p["spy_r"] is not None:
                    v = abs(p["ret"]) - abs(p["spy_r"]) if p["direction"] == "volatile" else _signed(p["direction"], p["ret"] - p["spy_r"])
                    item["vs_spy"] = round(v, 4)
                    if p["entry_date"] < today_s:
                        tracked += 1
                        ahead += v > 0
                b = bench.get(p["direction"])
                if b and p["id"] not in b[2]:
                    e = abs(p["ret"]) - abs(b[0]) if p["direction"] == "volatile" else _signed(p["direction"], p["ret"] - b[0])
                    item["vs_simple"] = round(e, 4)
                    item["simple"] = b[1] or "the other picks"
            items.append(item)
        # the user's part: is the call itself playing out? (theme vs the S&P 500, in the direction they called)
        call = None
        core = r["direction"]
        spy_r = next((p["spy_r"] for p in ps if p["spy_r"] is not None), None)
        theme = bench.get(core)
        if theme is None:
            same = [p["ret"] for p in ps if p["direction"] == core and p["shown"]]
            theme = (sum(same) / len(same), None, set()) if same else None
        if theme and spy_r is not None and core in ("bullish", "bearish", "volatile") and r["as_of_date"] < today_s:
            v = abs(theme[0]) - abs(spy_r) if core == "volatile" else _signed(core, theme[0] - spy_r)
            call = {"playing_out": v > 0, "vs_spy": round(v, 4), "measured_by": theme[1] or "your picks"}
            calls_tracked += 1
            calls_right += v > 0
        out.append({"belief_id": r["id"], "text": r["text"], "created_at": r["created_at"],
                    "summary": interp.get("summary"), "direction": r["direction"],
                    "horizon_days": r["horizon_days"], "picks": items, "call": call})
    summary = None
    if tracked or calls_tracked:
        summary = {"tracked": tracked, "ahead": ahead, "calls": calls_tracked, "calls_playing_out": calls_right}
    return {"beliefs": out, "summary": summary, "as_of": today_s}


# ---------------- one-year replay ----------------

def replay(tickers: list[str], directions: list[str], days: int = 365) -> dict:
    """How these picks did over the past `days`, vs SPY, from real daily closes. No Claude call."""
    days = int(max(30, min(days, 365 * 3)))
    import bisect
    end_d = market.today()
    start_s = (end_d - timedelta(days=days)).isoformat()
    try:
        sdates, scloses = market.daily_closes("SPY")
    except Exception as e:
        raise market.MarketDataError(f"no SPY history: {e}")
    i0 = bisect.bisect_left(sdates, start_s)
    if i0 >= len(sdates) - 5:
        raise market.MarketDataError("not enough history")
    axis = sdates[i0:]
    step = max(1, len(axis) // 52)
    marks = axis[::step] + ([axis[-1]] if axis[-1] not in axis[::step] else [])
    spy0 = scloses[i0]
    spy_pts = [round(scloses[bisect.bisect_left(sdates, d)] / spy0 - 1, 4) for d in marks]

    picks, series = [], []
    for t, dirn in zip(tickers[:5], directions[:5]):
        try:
            dates, closes = market.daily_closes(t)
        except Exception:
            continue
        j0 = bisect.bisect_left(dates, axis[0])
        if j0 >= len(dates) or dates[j0] > (end_d - timedelta(days=days - 10)).isoformat():
            continue  # listed too recently for a fair replay
        p0 = closes[j0]
        pts = []
        for d in marks:
            k = bisect.bisect_right(dates, d) - 1
            pts.append(round(closes[max(k, j0)] / p0 - 1, 4))
        ret = closes[-1] / p0 - 1
        sign = -1.0 if dirn == "bearish" else 1.0
        if dirn == "volatile":
            vs, right = abs(ret) - abs(spy_pts[-1]), abs(ret) > max(0.1, abs(spy_pts[-1]))
        else:
            vs, right = sign * (ret - spy_pts[-1]), sign * ret > 0
        picks.append({"ticker": t, "direction": dirn, "return": round(ret, 4), "vs_spy": round(vs, 4), "right": right})
        series.append(pts)
    if not picks:
        raise market.MarketDataError("no history for these picks")
    basket = [round(sum(s[i] for s in series) / len(series), 4) for i in range(len(marks))]
    bull = sum(1 for p in picks if p["direction"] != "bearish") >= len(picks) / 2
    return {
        "days": days, "start": axis[0], "end": axis[-1], "dates": marks,
        "basket": basket, "spy": spy_pts, "picks": picks,
        "basket_return": basket[-1], "spy_return": spy_pts[-1],
        "belief_right": (basket[-1] > 0) if bull else (basket[-1] < 0),
        "beat_spy": (basket[-1] > spy_pts[-1]) if bull else (basket[-1] < spy_pts[-1]),
    }
