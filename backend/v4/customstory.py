"""
"Make a story about this": a fresh Story-mode story for anything someone searches on the News page.

News search (newssearch.py) only finds stories the app already picked this week. This module goes further: for any
company, ticker or topic ("uranium", "Costco earnings") it fetches that subject's real recent headlines from the
news source, and Claude writes one story from them in the same cards as "Moving now" (hook, what happened, why it
matters, the twist, who it moves, your call).

Honesty rules: every fact comes from the fetched headlines and summaries (numbers on figure cards must be written
in them, the same `_grounded` check as Story mode), the story lists the headlines it was built from, and when the
news source has nothing recent on the subject the answer says so instead of writing one.

Cost rules: one story per subject per day, shared by everyone (kv_cache), a cap per person per day and a cap for the
whole app per day. A cached story costs nothing and doesn't count against either cap.
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

from . import db, market, movers, newssearch

log = logging.getLogger(__name__)

KEY = "custom:v1:"            # custom:v1:<YYYY-MM-DD>:<hash of the subject> -> the day's story
COUNT_KEY = "custom:n:"       # custom:n:<YYYY-MM-DD>:<hash of who> -> stories that person made today
PER_PERSON = int(os.getenv("MP_CUSTOM_STORY_PER_DAY", "5"))
PER_DAY = int(os.getenv("MP_CUSTOM_STORY_DAILY_MAX", "150"))
MAX_SOURCES = 8
MAX_AGE_DAYS = 14
_lock = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}
_news_cache: dict[str, tuple[float, list[dict]]] = {}
_none_cache: dict[str, tuple[float, dict]] = {}  # subjects with no news, remembered for an hour

TICKERS_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["tickers"],
    "properties": {"tickers": {"type": "array", "items": {"type": "string"}}},
}
TICKERS_PROMPT = """Name the 3 to 5 US-listed stocks or ETFs whose news is most likely to be about the topic the user
types (for "uranium": CCJ, UEC, URA, NXE). Only real, currently listed US tickers. If the topic isn't about markets,
companies or the economy at all, return an empty list."""

CUSTOM_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["used", "title", "hunch", "why_short", "companies"] + movers.STORY_SCHEMA["required"],
    "properties": {
        "used": {"type": "array", "items": {"type": "integer"}},
        "title": {"type": "string"},
        "hunch": {"type": "string"},
        "why_short": {"type": "string"},
        "companies": movers.SCHEMA["properties"]["items"]["items"]["properties"]["companies"],
        **movers.STORY_SCHEMA["properties"],
    },
}

CUSTOM_PROMPT = """Someone searched a finance news app for a subject. You get the subject and the only facts you may
use: recent headlines (with summaries) about it, numbered. Tell ONE story about what is going on with the subject,
built from these headlines. If they cover several things, tell the most important one. Never add facts, numbers,
dates or names that aren't written in them; if they say little, say little. Plain English, no jargon, no tickers
in the story text, no hype words like "massive" or "insane".

- used: the numbers of the headlines your story relies on.
- title: a factual headline for your story, under 12 words, no hype, no tickers.
- hunch: what someone would believe if they took this news seriously, as a plain forward-looking sentence under
  14 words ("Uranium miners will keep benefiting from new reactor deals"). No tickers, no jargon.
- why_short: one short sentence on why it matters for companies.
- companies: 2 to 4 US-listed stocks or ETFs the story most directly moves (if the subject is one company, it comes
  first), with direction "up" or "down" if the hunch is right and a 6-10 word reason that agrees with the direction.
""" + movers.STORY_PROMPT.split("\n", 2)[2]


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _h(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:20]


def subject_key(q: str) -> str:
    """The same subject however it's typed ("Uranium", "uranium news", " URANIUM ") -> one story a day."""
    return " ".join(newssearch.terms(q.lstrip("$"))) or q.lower().strip()


def _get(k: str) -> Optional[dict]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (k,))
    try:
        return json.loads(row["v"]) if row else None
    except Exception:
        return None


def _put(k: str, v: Any) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
               (k, json.dumps(v), datetime.now(timezone.utc).isoformat()))


def used_today(who: str) -> int:
    return int((_get(f"{COUNT_KEY}{_today()}:{_h(who)}") or {}).get("n") or 0)


def _made_today() -> int:
    row = db.query_one("SELECT COUNT(*) AS n FROM kv_cache WHERE k LIKE ?", (f"{KEY}{_today()}:%",))
    return int((row or {}).get("n") or 0)


def _count(who: str) -> None:
    _put(f"{COUNT_KEY}{_today()}:{_h(who)}", {"n": used_today(who) + 1})


def _age_days(created_at: Any) -> Optional[float]:
    try:
        t = datetime.fromisoformat(str(created_at or "").replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 86400
    except ValueError:
        return None


def news_for(symbols: list[str]) -> list[dict]:
    """Recent headlines tagged with any of these tickers, with summaries, cached 20 minutes. [] when unavailable."""
    if not symbols:
        return []
    k = ",".join(sorted(symbols))
    now = time.time()
    with _lock:
        hit = _news_cache.get(k)
        if hit and now - hit[0] < 1200:
            return hit[1]
    try:
        r = market._session.get(f"{market._data_base()}/v1beta1/news", headers=market._headers(),
                                params={"symbols": k, "limit": 50, "sort": "desc", "include_content": "false"},
                                timeout=8)
        raw = r.json().get("news", []) if r.status_code == 200 else []
    except Exception:
        return []
    out = [_clean(n) for n in raw]
    out = [n for n in out if n]
    with _lock:
        if len(_news_cache) > 300:
            _news_cache.clear()
        _news_cache[k] = (now, out)
    return out


def _clean(n: dict) -> Optional[dict]:
    h = re.sub(r"\s+", " ", str(n.get("headline") or "")).strip()
    if not h or len(h) > 220:
        return None
    syms = [str(s).upper() for s in n.get("symbols") or []]
    return {"headline": h, "source": n.get("source") or "", "created_at": n.get("created_at") or "",
            "summary": re.sub(r"<[^>]+>", "", str(n.get("summary") or "")).strip()[:500],
            "url": movers.story_url(n.get("url"), syms), "symbols": syms}


def _mentions(n: dict, ts: list[str]) -> bool:
    ws = newssearch._words(f"{n.get('headline')} {n.get('summary')}")
    return bool(ts) and all(any(w.startswith(t) for w in ws) for t in ts)


def _ask(client: Any, system: str, schema: dict, content: str, max_tokens: int) -> Optional[dict]:
    try:
        from .interpreter import _client
        client = client or _client()
        resp = client.messages.create(
            model=movers.MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": content}],
            extra_body={"output_config": {"effort": "low", "format": {"type": "json_schema", "schema": schema}}},
        )
        text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
        return json.loads(text)
    except Exception as e:  # a custom story must never break the page
        log.warning("customstory: Claude step failed: %s", e)
        return None


def _resolve_company(q: str) -> Optional[dict]:
    """The one company the search names, if any ("nvidia", "$NVDA", "Costco earnings")."""
    pool = list(movers.archived())
    co = newssearch._company(q, pool, topic_hits=False)
    if co and not co.get("guess"):
        return co
    ts = newssearch.terms(q)
    for i in range(len(ts), 0, -1):  # "costco earnings" -> "costco"
        sym = newssearch._KNOWN.get(" ".join(ts[:i]))
        if sym:
            try:
                info = market.asset_info(sym)
            except Exception:
                info = None
            if info:
                return {"ticker": info["symbol"], "name": info.get("name") or ""}
    return None


def gather(q: str, client: Any = None) -> tuple[Optional[dict], list[dict], bool]:
    """(company or None, up to MAX_SOURCES recent headlines about the subject newest first, asked_claude)."""
    ts = newssearch.terms(q.lstrip("$"))
    company = _resolve_company(q)
    asked = False
    if company:
        sym = company["ticker"]
        mine = [n for n in news_for([sym]) if sym in n["symbols"]]
        name_ts = [w for w in newssearch._words(company.get("name")) if w not in movers._NAME_FILLER][:1]
        extra = [t for t in ts if t not in name_ts and t.upper() != sym.upper().replace(".", "")
                 and t != sym.lower()]
        focused = [n for n in mine if _mentions(n, extra)] if extra else []
        found = focused + [n for n in mine if n not in focused]  # "Costco earnings": earnings headlines first
    else:
        syms: list[str] = []
        if os.getenv("ANTHROPIC_API_KEY") or client:
            asked = True
            d = _ask(client, TICKERS_PROMPT, TICKERS_SCHEMA, q, 300) or {}
            for t in d.get("tickers") or []:
                t = str(t).upper().strip().lstrip("$")
                if not movers._TICKER.match(t) or t in syms:
                    continue
                try:
                    ok = market.asset_info(t)
                except Exception:
                    ok = None
                if ok:
                    syms.append(t)
                if len(syms) == 5:
                    break
        pool = news_for(syms) + [_clean(n) or {} for n in market.headlines(50)]
        pool += [dict(a, symbols=[c.get("ticker") for c in a.get("companies") or []]) for a in movers.archived()]
        found = [n for n in pool if n.get("headline") and _mentions(n, ts)]
    seen, out = set(), []
    for n in found:
        key = n["headline"].lower()[:60]
        age = _age_days(n.get("created_at"))
        if key in seen or age is None or age > MAX_AGE_DAYS:
            continue
        seen.add(key)
        out.append({k: n.get(k) or "" for k in ("headline", "source", "created_at", "summary", "url")})
    if company:  # newest first, but the focused ones keep their head start
        out = out[:MAX_SOURCES]
    else:
        out = sorted(out, key=lambda n: str(n["created_at"]), reverse=True)[:MAX_SOURCES]
    return company, out, asked


def _write(q: str, company: Optional[dict], sources: list[dict], client: Any = None) -> Optional[dict]:
    """Claude's story from the sources, checked: figures grounded, hook whole, companies real. None on failure."""
    lines = [f"{i}. {n['headline']}" + (f"\n   {n['summary']}" if n.get("summary") else "") for i, n in enumerate(sources)]
    subj = f"{q}" + (f" (the company {company['ticker']}, {company.get('name') or ''})" if company else "")
    d = _ask(client, CUSTOM_PROMPT, CUSTOM_SCHEMA, f"Subject: {subj}\n\nHeadlines:\n" + "\n".join(lines), 2500)
    if not d:
        return None
    used = sorted({int(i) for i in d.get("used") or [] if isinstance(i, int) and 0 <= i < len(sources)}) or list(range(len(sources)))
    based = [sources[i] for i in used]
    source = "\n".join(f"{n['headline']}\n{n.get('summary') or ''}" for n in sources)
    figs = [{k: movers._clip(f.get(k), 28) for k in ("label", "before_label", "before", "after_label", "after")}
            for f in d.get("figures") or [] if isinstance(f, dict) and movers._grounded(f, source)]
    companies = []
    for c in movers._clean_companies(d.get("companies"), []):
        try:
            ok = market.asset_info(c["ticker"])
        except Exception:
            ok = c  # lookup down: keep it rather than empty the card
        if ok:
            companies.append(c)
    if company and company["ticker"] not in {c["ticker"] for c in companies}:
        companies = [{"ticker": company["ticker"], "direction": None, "why": "The company you searched"}] + companies[:3]
    title = movers._clip(d.get("title"), 110) or based[0]["headline"]
    hunch = re.sub(r"\s+", " ", str(d.get("hunch") or "")).strip()[:140] or title
    newest = max((n["created_at"] for n in based), default="")
    fb = movers._fallback_story({"headline": title, "summary": "", "why": ""})
    st = {"hook_big": movers._hook(d.get("hook_big"), source) or fb["hook_big"],
          "hook_line": movers._clip(d.get("hook_line"), 120), "happened": movers._sentences(d.get("happened"), 320),
          "figures": figs[:2], "why": movers._sentences(d.get("why"), 240),
          "twist": movers._sentences(d.get("twist"), 200), "ai": True}
    if not st["happened"] or not st["why"]:
        return None
    item = {"headline": title, "source": f"Written for your search from {len(based)} headline{'s' if len(based) != 1 else ''}",
            "url": "", "created_at": newest, "summary": "", "hunch": hunch,
            "why": movers._clip(d.get("why_short"), 200), "companies": companies, "custom": True, "q": q,
            "sources": based}
    return {"story": st, "item": item, "made_at": datetime.now(timezone.utc).isoformat()}


def _priced(out: dict) -> dict:
    """Today's prices on the companies (re-read every time, like the feed; the story itself is cached)."""
    item = out["item"]
    syms = sorted({c["ticker"] for c in item["companies"]} | {movers.BENCH})
    snaps = movers._snapshots(syms)
    bench = snaps.get(movers.BENCH) or {}
    item = dict(item, companies=[movers._with_timing(movers._vs_market(dict(c, **snaps.get(c["ticker"], {})), bench),
                                                     item.get("created_at")) for c in item["companies"]])
    return dict(out, item=item)


def make(q: str, who: str, client: Any = None) -> dict:
    """The day's story about q, writing it if nobody has today. Always returns a dict: with "story" and "item",
    or with story None and a plain-English "reason" (code: short, no_news, limit, busy, failed)."""
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:60]
    subj = subject_key(q)
    base = {"q": q, "story": None, "item": None, "per_day": PER_PERSON}
    if len(subj.replace(" ", "")) < 2:
        return dict(base, code="short", reason="Type at least 2 letters.")
    key = f"{KEY}{_today()}:{_h(subj)}"
    hit = _get(key)
    if hit:
        return dict(base, **_priced(hit), cached=True, left=max(0, PER_PERSON - used_today(who)))
    with _lock:
        neg = _none_cache.get(subj)
        if neg and time.time() - neg[0] < 3600:
            return dict(base, **neg[1])
        lk = _key_locks.setdefault(key, threading.Lock())
    if not os.getenv("ANTHROPIC_API_KEY") and not client:
        return dict(base, code="failed", reason="Writing new stories is switched off right now.")
    left = PER_PERSON - used_today(who)
    if left <= 0:
        return dict(base, code="limit", left=0,
                    reason=f"You've made {PER_PERSON} new stories today, the daily limit. Stories other people already "
                           "made today still open, and you can make more tomorrow.")
    if _made_today() >= PER_DAY:
        return dict(base, code="busy", left=left,
                    reason="We've written as many new stories as we can today. Try again tomorrow.")
    with lk:
        hit = _get(key)  # someone else may have just written it
        if hit:
            return dict(base, **_priced(hit), cached=True, left=left)
        company, sources, asked = gather(q, client)
        if not sources:
            if asked:
                _count(who)
            what = company["ticker"] if company else f"“{q}”"
            neg = {"code": "no_news", "reason": f"Our news source has nothing on {what} from the past {MAX_AGE_DAYS} days, "
                                                "so there's nothing real to build a story on. Try a company name, a "
                                                "ticker or a broader word."}
            with _lock:
                if len(_none_cache) > 500:
                    _none_cache.clear()
                _none_cache[subj] = (time.time(), neg)
            return dict(base, **neg, left=max(0, left - (1 if asked else 0)))
        _count(who)
        out = _write(q, company, sources, client)
        if not out:
            return dict(base, code="failed", left=left - 1, reason="The story couldn't be written just now. Try again in a minute.")
        _put(key, out)
        try:  # old days' stories and counts
            old = datetime.fromtimestamp(time.time() - 3 * 86400, timezone.utc).isoformat()
            db.execute("DELETE FROM kv_cache WHERE k LIKE ? AND created_at < ?", ("custom:%", old))
        except Exception:
            pass
    return dict(base, **_priced(out), cached=False, left=left - 1)
