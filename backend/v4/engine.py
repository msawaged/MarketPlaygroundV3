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


def _cached_interpretation(norm: str, risk: str) -> Optional[tuple[dict, dict]]:
    key = hashlib.sha1(f"{norm}|{risk}".encode()).hexdigest()
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
    cached = None if backfill else _cached_interpretation(norm, risk_profile)
    if cached:
        interp, usage = cached
    else:
        context = learning.build_context(belief)
        interp, usage = interpreter.interpret(
            belief, risk_profile, as_of=as_of if backfill else None,
            context=context, model=model, client=claude_client,
        )
        if not backfill:
            _store_interpretation(norm, risk_profile, interp, usage)

    belief_id = f"b-{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "belief_id": belief_id, "user_id": user_id, "risk_profile": risk_profile,
        "interpretation": {k: interp.get(k) for k in ("summary", "causal_chain", "themes", "horizon_days", "conviction", "direction")},
        "engine": "v4", "usage": usage,
    }

    if not interp.get("is_market_belief") or not interp.get("candidates"):
        return {**base, "strategy": None, "picks": [], "valid": False,
                "error": "not_a_market_belief",
                "reason": interp.get("note") or "I couldn't find a market angle in that. Try describing what you think will grow, shrink, or change."}

    # 3. validate candidates
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
    for i, v in enumerate(valid):
        v["features"] = records[i]
        v["nn_score"] = preds[i] if preds else None
        claude_part = v["score"] + learning.ticker_adjustment(stats.get(v["ticker"]))
        # NN predicts expected directional excess (~ -0.5..0.5); map to a 0-1-ish scale
        nn_part = 0.5 + 2.0 * preds[i] if preds else claude_part
        v["final_score"] = (1 - w) * claude_part + w * nn_part
        v["track"] = stats.get(v["ticker"])
    valid.sort(key=lambda v: v["final_score"], reverse=True)

    # 5. structures
    picks_out = []
    rows_picks, rows_themes = [], []
    for final_rank, v in enumerate(valid):
        sstats = learning.structure_stats(v["direction"], interp["horizon_days"])
        structure, why = strategy.choose_structure(v["direction"], interp["horizon_days"], interp["conviction"], risk_profile, sstats)
        trade = strategy.build_trade(structure, v["ticker"], v["price"], v["mkt"]["vol60"], date.fromisoformat(v["entry_date"]), interp["horizon_days"])
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
            v["entry_date"], v["price"], structure, db.dumps(trade), db.dumps(v["features"]),
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
                              nn_score, final_score, final_rank, shown, entry_date, entry_price, structure, legs, features)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
