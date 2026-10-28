"""
Claude belief interpreter — ONE call per belief.

Turns any belief ("potatoes are in demand", "plumbing demand will be high",
"AAPL hits 250") into: what it means, direction, horizon, conviction, themes,
the chain of reasoning, and 5-12 candidate tickers/ETFs that express it.

The call is given what the system has learned from ALL users (similar past
beliefs and how their picks were graded), so Claude's suggestions improve as
the shared track record grows.

Env:
  ANTHROPIC_API_KEY
  MP_CLAUDE_MODEL         default claude-sonnet-5-5
  MP_CLAUDE_EFFORT        default low   (low | medium | high)
  MP_CLAUDE_MAX_TOKENS    default 3000
"""
from __future__ import annotations

import json
import os
from datetime import date
from typing import Any, Optional

DEFAULT_MODEL = os.getenv("MP_CLAUDE_MODEL", "claude-sonnet-5-5")

# $ per million tokens (input, output). Used only for cost tracking.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_market_belief", "note", "summary", "direction", "horizon_days",
        "conviction", "themes", "causal_chain", "candidates",
        "wrong_if", "exit_rule", "clarify_question", "clarify_options", "target_price",
    ],
    "properties": {
        "is_market_belief": {"type": "boolean"},
        "note": {"type": "string"},
        "summary": {"type": "string"},
        "direction": {"type": "string", "enum": ["bullish", "bearish", "neutral", "volatile"]},
        "horizon_days": {"type": "integer"},
        "conviction": {"type": "string", "enum": ["low", "medium", "high"]},
        "themes": {"type": "array", "items": {"type": "string"}},
        "causal_chain": {"type": "string"},
        "wrong_if": {"type": "array", "items": {"type": "string"}},
        "exit_rule": {"type": "string"},
        "clarify_question": {"type": "string"},
        "target_price": {"type": "number"},
        "clarify_options": {"type": "array", "items": {"type": "string"}},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ticker", "name", "exposure", "direction", "rationale", "score", "strategy", "strategy_why"],
                "properties": {
                    "ticker": {"type": "string"},
                    "name": {"type": "string"},
                    "exposure": {"type": "string", "enum": ["direct", "supplier", "beneficiary", "etf", "inverse"]},
                    "direction": {"type": "string", "enum": ["bullish", "bearish", "volatile"]},
                    "rationale": {"type": "string"},
                    "score": {"type": "number"},
                    "strategy": {"type": "string"},
                    "strategy_why": {"type": "string"},
                },
            },
        },
    },
}

SYSTEM_PROMPT = """You are the belief interpreter for MarketPlayground, an app where people type what they believe about the world and get trade ideas that express that belief.

Beliefs can be anything: a specific stock call ("AAPL will hit 250"), a sector view ("plumbing demand will be high"), a consumer trend ("potatoes are in demand"), a macro view ("rates will stay high"), or a cultural observation. Your job is to work out what the belief implies for publicly traded US securities.

Return:
- is_market_belief: false only if the text has no plausible market implication at all (greetings, nonsense). Then explain briefly in note and leave candidates empty.
- summary: one sentence restating the belief as a market view.
- direction: the overall stance on the core theme (bullish = the theme benefits, bearish = it suffers, neutral = range-bound / calm, volatile = a BIG move is coming but the direction is unclear, e.g. "this earnings report will be a shock either way", "the FDA decision will make or break them", "it's going to crash or moon").
- horizon_days: how long the belief needs to play out (use the user's wording; default 180 for open-ended trends, 30 for event-driven).
- conviction: from the user's wording ("definitely", "might", "I think").
- themes: 2-5 short lowercase tags that a different user with a similar idea would also produce (e.g. "plumbing", "housing", "water infrastructure"). Prefer common, reusable words over clever ones.
- causal_chain: 1-3 sentences: belief -> what changes in the real economy -> who earns more or less.
- candidates: 5 to 12 US-listed stocks or ETFs that express the belief, best first. Mix the most direct pure-plays, key suppliers or beneficiaries, and one relevant sector ETF when one exists. Each candidate has its own direction (a belief can be bullish for one company and bearish for another; use volatile for a company expected to make a big move either way). score is 0-1: how directly and cleanly that ticker expresses the belief.

- wrong_if: 2-3 short, observable signs that the belief is failing (e.g. "Housing starts fall two months in a row"). Plain words, no jargon.
- exit_rule: one plain sentence a beginner can follow to get out (e.g. "Sell if it drops 10% from where you bought, or if two of the signs above happen.").
- clarify_question / clarify_options: if ONE short question would clearly change which companies fit (region, time frame, which part of the trend), ask it with 2-3 short tappable options (each under 25 characters). Otherwise return "" and []. Still return your best-guess candidates either way.

- target_price: if the belief names a price target for the main company ("AAPL hits 250"), that number; otherwise 0.
- strategy / strategy_why: for each candidate, the single best way to trade it from the STRATEGY LIBRARY below, given its direction, the time frame, the user's risk profile and the user's preferences (if any). One plain sentence on why (no jargon, e.g. "Earns cash while you wait to buy it cheaper."). Respect the preferences: "shares" means only Buy Stock / Sell / Avoid; "options" means only options strategies; a goal means pick a strategy that serves it. Careful (conservative) users: only defined-risk or income strategies (Buy Stock, Bull Call Spread, Bear Put Spread, Cash-Secured Put, Covered Call, Protective Put, Collar, Sell / Avoid).

STRATEGY LIBRARY (name: when it fits):
- Buy Stock: bullish, simplest; also for funds/ETFs.
- Sell / Avoid: bearish or no clear trade; stay out or trim.
- Long Call: strongly bullish, wants big upside, accepts losing the premium.
- Bull Call Spread: bullish, wants a cheaper bet with capped risk and capped gain.
- Bull Put Spread: mildly bullish, wants income; keeps the credit if the stock stays up.
- Cash-Secured Put: bullish long-term, happy to buy lower; gets paid to wait.
- Covered Call: owns or will own 100 shares, mildly bullish or flat, wants income.
- Protective Put: owns the stock and worries about a drop; insurance with open upside.
- Collar: owns the stock, wants cheap protection, OK capping upside.
- Long Put: strongly bearish, wants big payoff from a fall.
- Bear Put Spread: bearish with capped risk.
- Bear Call Spread: mildly bearish, wants income; keeps the credit if the stock stays down.
- Iron Condor: expects a calm, range-bound stock; income.
- Iron Butterfly: expects the stock to sit very near today's price; bigger income, narrower.
- Long Call Butterfly: has a specific target price on a date (needs target_price).
- Long Straddle: expects a big move either way, wants the most exposure.
- Long Strangle: expects a big move either way, wants it cheaper.

Rules:
- Only real, currently listed US tickers in uppercase. No OTC, no foreign-only listings, no crypto.
- Prefer liquid names. Do not pad the list with weak or generic picks; SPY/QQQ only if the belief is truly about the whole market.
- When "as of" is given, reason only from what was known by that date and do not use knowledge of later price moves.
- Use the shared track record when provided: lean toward tickers that have expressed similar beliefs well, and away from ones that have repeatedly failed or that users rejected, unless you have a specific reason.
- Keep rationales to one short sentence each."""


class InterpreterError(RuntimeError):
    pass


def _client():
    import anthropic

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise InterpreterError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=key)


def _context_block(context: Optional[dict]) -> str:
    if not context:
        return ""
    lines: list[str] = []
    sims = context.get("similar") or []
    if sims:
        lines.append("Shared track record — similar past beliefs from all users and how their picks did (directional return vs SPY):")
        for s in sims:
            picks = ", ".join(
                f"{p['ticker']} {p['result']}" for p in s.get("picks", [])
            ) or "not graded yet"
            lines.append(f"- \"{s['text']}\" [{', '.join(s.get('themes') or [])}]: {picks}")
    stats = context.get("ticker_stats") or []
    if stats:
        lines.append("Tickers with the most history on these themes:")
        for t in stats:
            fb = f", users 👍{t['up']} 👎{t['down']}" if (t.get("up") or t.get("down")) else ""
            lines.append(f"- {t['ticker']}: {t['n']} graded, avg {t['mean']:+.1%} vs SPY, hit rate {t['hit']:.0%}{fb}")
    return "\n".join(lines)


def build_user_message(belief: str, risk_profile: str, as_of: Optional[date], context: Optional[dict],
                       prefs: Optional[dict] = None) -> str:
    parts = [f"Belief: {belief.strip()}", f"User risk profile: {risk_profile}"]
    if prefs and (prefs.get("instrument", "auto") != "auto" or prefs.get("goal")):
        parts.append(f"User preferences: trade with {prefs.get('instrument', 'auto')}"
                     + (f"; what matters most: {prefs['goal']}" if prefs.get("goal") else ""))
    if as_of:
        parts.append(f"As of: {as_of.isoformat()}")
    ctx = _context_block(context)
    if ctx:
        parts.append(ctx)
    return "\n\n".join(parts)


def _sanitize(out: dict) -> dict:
    out["horizon_days"] = int(max(7, min(int(out.get("horizon_days") or 180), 730)))
    out["themes"] = [t.strip().lower() for t in (out.get("themes") or []) if t and t.strip()][:5]
    seen: set[str] = set()
    cands = []
    for c in out.get("candidates") or []:
        t = (c.get("ticker") or "").upper().strip().replace("-", ".")  # Alpaca uses BRK.B
        if not t or t in seen or not t.replace(".", "").isalpha() or len(t) > 6:
            continue
        seen.add(t)
        c["ticker"] = t
        c["score"] = float(max(0.0, min(1.0, c.get("score") or 0.5)))
        c["strategy"] = str(c.get("strategy") or "").strip()
        c["strategy_why"] = str(c.get("strategy_why") or "").strip()[:200]
        cands.append(c)
    out["candidates"] = cands[:12]
    out["wrong_if"] = [str(w).strip() for w in (out.get("wrong_if") or []) if str(w).strip()][:3]
    out["exit_rule"] = str(out.get("exit_rule") or "").strip()
    try:
        out["target_price"] = max(0.0, float(out.get("target_price") or 0))
    except (TypeError, ValueError):
        out["target_price"] = 0.0
    opts = [str(o).strip()[:40] for o in (out.get("clarify_options") or []) if str(o).strip()][:3]
    q = str(out.get("clarify_question") or "").strip()
    out["clarify_question"], out["clarify_options"] = (q, opts) if q and len(opts) >= 2 else ("", [])
    return out


def interpret(
    belief: str,
    risk_profile: str = "moderate",
    as_of: Optional[date] = None,
    context: Optional[dict] = None,
    model: Optional[str] = None,
    client: Any = None,
    prefs: Optional[dict] = None,
) -> tuple[dict, dict]:
    """Returns (interpretation, usage) where usage = {model, input_tokens, output_tokens, cost_usd}."""
    model = model or DEFAULT_MODEL
    client = client or _client()
    resp = client.messages.create(
        model=model,
        max_tokens=int(os.getenv("MP_CLAUDE_MAX_TOKENS", "3000")),
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": build_user_message(belief, risk_profile, as_of, context, prefs)}],
        extra_body={
            "output_config": {
                "effort": os.getenv("MP_CLAUDE_EFFORT", "low"),
                "format": {"type": "json_schema", "schema": SCHEMA},
            }
        },
    )
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), None)
    if not text:
        raise InterpreterError(f"no text in Claude response (stop_reason={getattr(resp, 'stop_reason', '?')})")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InterpreterError(f"Claude returned invalid JSON: {e}") from e

    u = getattr(resp, "usage", None)
    in_tok = int(getattr(u, "input_tokens", 0) or 0) + int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    cached = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    out_tok = int(getattr(u, "output_tokens", 0) or 0)
    pin, pout = PRICES.get(model, (2.0, 10.0))
    cost = (in_tok * pin + cached * pin * 0.1 + out_tok * pout) / 1_000_000
    usage = {"model": model, "input_tokens": in_tok + cached, "output_tokens": out_tok, "cost_usd": round(cost, 6)}
    return _sanitize(data), usage
