"""
"Moving now": today's market headlines, each turned into a plain-English hunch and the companies it moves.

One Claude call turns the latest batch of headlines into hunches. The result is shared by everyone and stored
in kv_cache, so it costs a few dozen calls a day no matter how many people open the page. Without Claude
(no key, error, or budget), the feed still works: the headline itself is the hunch and the article's tagged
tickers are the companies.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from . import db, market

log = logging.getLogger(__name__)

TTL = int(os.getenv("MP_MOVERS_TTL_SECONDS", "1800"))  # refresh at most every 30 minutes
MODEL = os.getenv("MP_MOVERS_MODEL", "claude-haiku-5-5")
KEY = "movers:v1"
MAX_ITEMS = 8
_lock = threading.Lock()
_TICKER = re.compile(r"^[A-Z][A-Z.]{0,5}$")

SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["n", "keep", "hunch", "why", "companies"],
                "properties": {
                    "n": {"type": "integer"},
                    "keep": {"type": "boolean"},
                    "hunch": {"type": "string"},
                    "why": {"type": "string"},
                    "companies": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["ticker", "direction", "why"],
                            "properties": {
                                "ticker": {"type": "string"},
                                "direction": {"type": "string", "enum": ["up", "down"]},
                                "why": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}

PROMPT = """You turn market news into hunches a regular person could believe or doubt.

For each numbered headline:
- keep: false for routine noise: analyst rating or price-target changes ("maintains", "raises price target", "upgrades"),
  a single small company's earnings numbers beat/miss, dividend or buyback notices, price moves with no reason, ads,
  listicles, or anything too vague. keep: true for news about the wider world that touches several companies:
  demand shifts, prices of commodities, policy and rates, new technology, consumer habits, big company moves that
  ripple to suppliers and rivals. Keep at most 8, the most interesting first.
- hunch: what someone would believe if they took this news seriously, as a plain sentence under 14 words,
  written as a forward-looking belief ("Weight-loss drugs will keep cutting snack sales"). No tickers, no jargon.
- why: one short sentence on why it matters for companies.
- companies: 2 to 4 US-listed stocks or ETFs it most directly moves, with direction "up" or "down" if the hunch
  is right and a 6-10 word reason. Prefer the tagged tickers when they fit. Only real, currently listed tickers.

Return every headline once, by its number."""


def _snapshots(symbols: list[str]) -> dict[str, dict]:
    """{sym: {"price", "change"}} where change is today's move vs the last close (fraction)."""
    if not symbols:
        return {}
    try:
        r = market._session.get(f"{market._data_base()}/v2/stocks/snapshots", headers=market._headers(),
                                params={"symbols": ",".join(symbols), "feed": os.getenv("ALPACA_DATA_FEED", "iex")},
                                timeout=8)
        r.raise_for_status()
        raw = r.json() or {}
    except Exception:
        return {}
    out = {}
    for sym, s in raw.items():
        try:
            price = float((s.get("latestTrade") or {}).get("p") or (s.get("dailyBar") or {}).get("c") or 0)
            prev = float((s.get("prevDailyBar") or {}).get("c") or 0)
            if price > 0:
                out[sym] = {"price": round(price, 2), "change": round(price / prev - 1, 4) if prev > 0 else None}
        except (TypeError, ValueError):
            continue
    return out


_last_error = {"v": ""}


def _ask_claude(news: list[dict], client: Any = None) -> Optional[dict[int, dict]]:
    if not client and not os.getenv("ANTHROPIC_API_KEY"):
        _last_error["v"] = "no Claude key"
        return None
    try:
        from .interpreter import _client
        client = client or _client()
        lines = [f"{i}. {n['headline']}" + (f"  [tagged: {', '.join(n['symbols'])}]" if n.get("symbols") else "")
                 for i, n in enumerate(news)]
        resp = client.messages.create(
            model=MODEL, max_tokens=5000, system=PROMPT,
            messages=[{"role": "user", "content": "\n".join(lines)}],
            extra_body={"output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}},
        )
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        data = json.loads(text)
        out = {int(it["n"]): it for it in data.get("items", []) if isinstance(it, dict) and "n" in it}
        if out and min(out) == 1 and 0 not in out:  # numbered from 1 instead of 0
            out = {k - 1: v for k, v in out.items()}
        _last_error["v"] = "" if out else "Claude returned no items"
        return out or None
    except Exception as e:  # the feed must never break because of this
        log.warning("movers: Claude step failed: %s", e)
        _last_error["v"] = f"Claude: {type(e).__name__}: {str(e)[:160]}"
        return None


def _clean_companies(raw: Any, tagged: list[str]) -> list[dict]:
    out, seen = [], set()
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        t = str(c.get("ticker") or "").upper().strip().lstrip("$")
        if not _TICKER.match(t) or t in seen:
            continue
        d = "down" if str(c.get("direction")).lower() == "down" else "up"
        out.append({"ticker": t, "direction": d, "why": str(c.get("why") or "")[:90]})
        seen.add(t)
        if len(out) == 4:
            break
    if not out:
        out = [{"ticker": t, "direction": None, "why": ""} for t in tagged[:3] if _TICKER.match(t)]
    return out


def _items(news: list[dict], ai: Optional[dict]) -> list[dict]:
    items = []
    for i, n in enumerate(news):
        a = (ai or {}).get(i)
        if ai is not None and (not a or not a.get("keep")):
            continue
        hunch = str((a or {}).get("hunch") or "").strip()[:140] or n["headline"]
        items.append({
            "headline": n["headline"], "source": n.get("source") or "", "url": n.get("url") or "",
            "created_at": n.get("created_at") or "",
            "hunch": hunch, "why": str((a or {}).get("why") or "").strip()[:200],
            "companies": _clean_companies((a or {}).get("companies"), n.get("symbols") or []),
        })
        if len(items) == MAX_ITEMS:
            break
    return items


def build(client: Any = None) -> dict:
    _last_error["v"] = ""
    news = [n for n in market.headlines(50) if n.get("headline")][:30]
    ai = _ask_claude(news, client) if news else None
    items = _items(news, ai)
    if ai is not None and not items:  # Claude kept nothing: fall back to the headlines themselves
        ai, items = None, _items(news, None)
    # drop tickers that aren't tradable US stocks (cheap: asset_info is cached per process)
    for it in items:
        ok = []
        for c in it["companies"]:
            try:
                if market.asset_info(c["ticker"]):
                    ok.append(c)
            except Exception:
                ok.append(c)  # lookup down: keep it rather than empty the card
        it["companies"] = ok
    items = [it for it in items if it["companies"]]
    diag = {"headlines": len(news), "error": _last_error["v"] or ((market.news_error["v"] or "no headlines from the news source") if not news else "")}
    return {"items": items, "built_at": datetime.now(timezone.utc).isoformat(), "ai": ai is not None, "diag": diag}


def _stored() -> Optional[dict]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (KEY,))
    if not row:
        return None
    try:
        return json.loads(row["v"])
    except Exception:
        return None


def _age(feed: dict) -> float:
    try:
        return time.time() - datetime.fromisoformat(feed["built_at"]).timestamp()
    except Exception:
        return 1e9


def feed(client: Any = None) -> dict:
    """The shared feed with live prices attached. Rebuilds at most every TTL seconds."""
    cur = _stored()
    ttl = TTL if (cur and cur.get("items")) else 120
    if not cur or _age(cur) > ttl:
        if _lock.acquire(blocking=cur is None):
            try:
                cur2 = _stored()
                if not cur2 or _age(cur2) > ttl:
                    fresh = build(client)
                    if fresh["items"] or not (cur and cur.get("items")):
                        db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
                        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                                   (KEY, json.dumps(fresh), fresh["built_at"]))
                        cur = fresh
                else:
                    cur = cur2
            finally:
                _lock.release()
    cur = dict(cur or {"items": [], "built_at": None, "ai": False})
    syms = sorted({c["ticker"] for it in cur["items"] for c in it["companies"]})
    snaps = _snapshots(syms)
    cur["items"] = [dict(it, companies=[dict(c, **snaps.get(c["ticker"], {})) for c in it["companies"]])
                    for it in cur["items"]]
    cur["market"] = market.clock()
    return cur
