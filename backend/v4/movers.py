"""
"Moving now": today's market headlines, each turned into a plain-English hunch and the companies it moves.

One Claude call turns the latest batch of headlines into hunches. The result is shared by everyone and stored
in kv_cache, so it costs a few dozen calls a day no matter how many people open the page. Without Claude
(no key, error, or budget), the feed still works: the headline itself is the hunch and the article's tagged
tickers are the companies.
"""
from __future__ import annotations

import hashlib
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
            model=MODEL, max_tokens=12000, system=PROMPT,  # 30 headlines of JSON overflowed 5000 (cut-off reply)
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
            "created_at": n.get("created_at") or "", "summary": n.get("summary") or "",
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


# ---------------------------------------------------------------------------------------------------------------
# Story mode: one news item told as 5-6 full-screen cards (hook, what happened, why it matters, the twist, who moves,
# your call). Written once per headline by Claude and shared by everyone (kv_cache), so it costs one small call per
# story no matter how many people open it. Numbers on the cards only ever come from the article itself.

STORY_KEY = "story:v1:"

STORY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["hook_big", "hook_line", "happened", "figures", "why", "twist"],
    "properties": {
        "hook_big": {"type": "string"},
        "hook_line": {"type": "string"},
        "happened": {"type": "string"},
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "before_label", "before", "after_label", "after"],
                "properties": {
                    "label": {"type": "string"},
                    "before_label": {"type": "string"},
                    "before": {"type": "string"},
                    "after_label": {"type": "string"},
                    "after": {"type": "string"},
                },
            },
        },
        "why": {"type": "string"},
        "twist": {"type": "string"},
    },
}

STORY_PROMPT = """You turn one market news story into a short, punchy story told on full-screen cards, like a great
finance explainer reel. Plain English, no jargon, no tickers in the text, no hype words like "massive" or "insane".

- hook_big: the attention-grabber, at most 4 words. Use a striking number from the article if there is one
  ("$51 billion", "Half a trillion", "Up 40%"); otherwise a short punchy phrase ("Shoppers are switching").
- hook_line: one sentence under 14 words that makes someone want to keep reading.
- happened: what happened, in at most 30 words.
- figures: 0 to 2 before/after comparisons, ONLY when both numbers are written in the headline or summary
  ("Cloud sales": "A year ago" "$15.2B" -> "Now" "$30.7B"; or "What Wall Street expected" vs "Actual").
  Copy the numbers exactly as written. Never estimate, round or invent a number. If unsure, return [].
- why: why it matters for companies and investors, as a short chain of cause and effect, at most 30 words.
- twist: the best honest reason this might NOT play out the way people expect (the skeptic's view), at most 25 words.
"""


def _story_key(headline: str) -> str:
    return STORY_KEY + hashlib.sha1(headline.strip().lower().encode()).hexdigest()[:20]


def _nums(text: str) -> set[str]:
    return {m.replace(",", "") for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def _grounded(fig: dict, source: str) -> bool:
    """A figure is kept only if every number on it is written in the article (no invented numbers)."""
    have = _nums(source)
    need = _nums(fig.get("before", "")) | _nums(fig.get("after", ""))
    return bool(_nums(fig.get("before", ""))) and bool(_nums(fig.get("after", ""))) and need <= have


def _clip(s: Any, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def _fallback_story(item: dict) -> dict:
    nums = re.findall(r"[$]?\d[\d,.]*\s?(?:%|billion|million|trillion|B|M)?", item["headline"])
    return {"hook_big": _clip(nums[0], 20) if nums else "Moving now", "hook_line": _clip(item["headline"], 110),
            "happened": _clip(item.get("summary") or item["headline"], 220), "figures": [],
            "why": _clip(item.get("why") or "News like this can shift which companies people want to own.", 220),
            "twist": "Markets react fast. Some of this may already be priced in, so the next move could surprise.",
            "ai": False}


def _write_story(item: dict, client: Any = None) -> dict:
    if not client and not os.getenv("ANTHROPIC_API_KEY"):
        return _fallback_story(item)
    source = f"{item['headline']}\n{item.get('summary') or ''}"
    companies = ", ".join(f"{c['ticker']} ({c.get('why') or c.get('direction') or ''})" for c in item.get("companies", []))
    try:
        from .interpreter import _client
        client = client or _client()
        resp = client.messages.create(
            model=MODEL, max_tokens=1500, system=STORY_PROMPT,
            messages=[{"role": "user", "content": f"Headline: {item['headline']}\nSummary: {item.get('summary') or '(none)'}\n"
                                                  f"What it could mean: {item.get('hunch') or ''}\nCompanies it touches: {companies}"}],
            extra_body={"output_config": {"effort": "low", "format": {"type": "json_schema", "schema": STORY_SCHEMA}}},
        )
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        d = json.loads(text)
    except Exception as e:  # a story must never break the page
        log.warning("movers: story step failed: %s", e)
        return _fallback_story(item)
    figs = []
    for f in d.get("figures") or []:
        if isinstance(f, dict) and _grounded(f, source):
            figs.append({k: _clip(f.get(k), 28) for k in ("label", "before_label", "before", "after_label", "after")})
    return {"hook_big": _clip(d.get("hook_big"), 28) or "Moving now", "hook_line": _clip(d.get("hook_line"), 120),
            "happened": _clip(d.get("happened"), 240), "figures": figs[:2], "why": _clip(d.get("why"), 240),
            "twist": _clip(d.get("twist"), 200), "ai": True}


def story(headline: str, client: Any = None) -> Optional[dict]:
    """The story for one headline in today's feed (None if it isn't in the feed: no arbitrary prompts)."""
    headline = (headline or "").strip()
    if not headline:
        return None
    cur = feed(client)
    item = next((it for it in cur.get("items", []) if it["headline"] == headline), None)
    if not item:
        return None
    key = _story_key(headline)
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (key,))
    st = None
    if row:
        try:
            st = json.loads(row["v"])
        except Exception:
            st = None
    if not st:
        st = _write_story(item, client)
        if st.get("ai"):  # only keep real stories; a fallback is retried next time
            db.execute("DELETE FROM kv_cache WHERE k = ?", (key,))
            db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                       (key, json.dumps(st), datetime.now(timezone.utc).isoformat()))
    return {"story": st, "item": item, "market": cur.get("market")}
