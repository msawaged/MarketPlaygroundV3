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
from datetime import date, datetime, timezone
from typing import Any, Optional

from . import db, market

log = logging.getLogger(__name__)

TTL = int(os.getenv("MP_MOVERS_TTL_SECONDS", "1800"))  # refresh at most every 30 minutes
MODEL = os.getenv("MP_MOVERS_MODEL", "claude-haiku-5-5")
KEY = "movers:v2"  # v2 (2026-11-18): v1 held cards whose hunch belonged to a neighbouring headline
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
                "required": ["n", "starts", "keep", "hunch", "why", "companies"],
                "properties": {
                    "n": {"type": "integer"},
                    "starts": {"type": "string"},
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
- n: its number; starts: its first 5 words, copied exactly (this is how your answer is matched to the headline).
- keep: false for routine noise: analyst rating or price-target changes ("maintains", "raises price target", "upgrades"),
  a single small company's earnings numbers beat/miss, dividend or buyback notices, price moves with no reason, ads,
  listicles, or anything too vague. keep: true for news about the wider world that touches several companies:
  demand shifts, prices of commodities, policy and rates, new technology, consumer habits, big company moves that
  ripple to suppliers and rivals. Keep at most 8, the most interesting first.
- hunch: what someone would believe if they took this news seriously, as a plain sentence under 14 words,
  written as a forward-looking belief ("Weight-loss drugs will keep cutting snack sales"). No tickers, no jargon.
- why: one short sentence on why it matters for companies.
- companies: 2 to 4 US-listed stocks or ETFs it most directly moves, with direction "up" or "down" if the hunch
  is right and a 6-10 word reason that says how the hunch helps ("up") or hurts ("down") that company; the reason
  must agree with the direction (never "up" with a reason about pressure on it). Prefer the tagged tickers when they fit. Only real, currently listed tickers.
  Tags can be foreign tickers that belong to a different US company (Centrica's London ticker CNA is CNA Financial,
  an insurer, in the US): use a ticker only if it is the US listing of that very company; leave out companies with
  no US listing.

Return every headline once, by its number."""


def _today_change(price: float, prev: float, snap: dict) -> Optional[float]:
    """Today's move, or None when it can't be trusted: the comparison close must be the session right before
    today's bar (a stale "previous" bar on the free feed would turn a week's move into "today"), and a move past
    40% is treated as a data error rather than shown."""
    if not (prev > 0):
        return None
    try:
        d_today = str((snap.get("dailyBar") or {}).get("t") or "")[:10]
        d_prev = str((snap.get("prevDailyBar") or {}).get("t") or "")[:10]
        if d_today and d_prev:
            gap = (date.fromisoformat(d_today) - date.fromisoformat(d_prev)).days
            if gap <= 0 or gap > 4:  # weekends and one-day holidays are fine; anything longer is stale
                return None
    except ValueError:
        return None
    ch = price / prev - 1
    return round(ch, 4) if abs(ch) <= 0.40 else None


def _snapshots(symbols: list[str]) -> dict[str, dict]:
    """{sym: {"price", "change", "change_day"}}: change is the latest session's move vs the close before it
    (fraction); change_day is that session's date (YYYY-MM-DD)."""
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
                ch = _today_change(price, prev, s)
                out[sym] = {"price": round(price, 2), "change": ch,
                            # the session the move belongs to, so a weekend screen says "Fri", not "today"
                            "change_day": (str((s.get("dailyBar") or {}).get("t") or "")[:10] or None) if ch is not None else None}
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
        out = _align([it for it in data.get("items", []) if isinstance(it, dict) and "n" in it], news)
        _last_error["v"] = "" if out else "Claude returned no items"
        return out or None
    except Exception as e:  # the feed must never break because of this
        log.warning("movers: Claude step failed: %s", e)
        _last_error["v"] = f"Claude: {type(e).__name__}: {str(e)[:160]}"
        return None


def _words(s: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(s or "").lower())


def _align(raw: list[dict], news: list[dict]) -> dict[int, dict]:
    """{headline index: Claude's answer}. Each answer echoes the start of its headline ("starts") and is filed under
    the headline it names, not just under its number: live 2026-11-18 4 AM ET, four cards in a row carried the
    neighbouring headline's hunch ("Sulnox Group PLC Secures New Canadian Patent" -> "Oil majors will keep
    struggling to buy assets in Egypt's gas fields"). An answer whose "starts" matches no headline is dropped.
    Answers without "starts" fall back to their number (with the old numbered-from-1 fix)."""
    heads = [_words(n.get("headline")) for n in news]
    out: dict[int, dict] = {}
    plain = [it for it in raw if not _words(it.get("starts"))]
    for it in raw:
        s = _words(it.get("starts"))
        if not s:
            continue
        k = min(3, len(s))
        try:
            hint = int(it["n"])
        except (TypeError, ValueError):
            hint = -9
        order = [hint, hint - 1, hint + 1] + list(range(len(news)))
        i = next((i for i in order if 0 <= i < len(news) and i not in out and heads[i][:k] == s[:k]), None)
        if i is None:
            log.warning("movers: answer %r matches no headline, dropped", it.get("starts"))
            continue
        out[i] = it
    if plain:
        by_n = {}
        for it in plain:
            try:
                by_n[int(it["n"])] = it
            except (TypeError, ValueError):
                continue
        if by_n and min(by_n) == 1 and 0 not in by_n:  # numbered from 1 instead of 0
            by_n = {k - 1: v for k, v in by_n.items()}
        for k, v in by_n.items():
            out.setdefault(k, v)
    return out


def _clean_companies(raw: Any, tagged: list[str], cap: int = 4) -> list[dict]:
    out, seen = [], set()
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        t = str(c.get("ticker") or "").upper().strip().lstrip("$")
        if not _TICKER.match(t) or t in seen:
            continue
        d = "down" if str(c.get("direction")).lower() == "down" else "up"
        out.append({"ticker": t, "direction": d, "why": _clip(c.get("why"), 110)})  # whole words: [:90] cut "Sociedad Quimica's s"
        seen.add(t)
        if len(out) == cap:
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
            "_tags": [str(t).upper() for t in n.get("symbols") or []],
        })
        if len(items) == MAX_ITEMS:
            break
    return items


_NAME_FILLER = {"the", "inc", "incorporated", "corp", "corporation", "co", "company", "class", "common", "stock",
                "shares", "ordinary", "plc", "ltd", "limited", "holdings", "holding", "group", "sa", "nv", "ag", "adr",
                "american", "depositary", "sponsored", "new"}


def _names_company(info: dict, ticker: str, item: dict) -> bool:
    """True when the story mentions the company: its ticker as a word, or the first real word of its name."""
    name = str(info.get("name") or "")
    if not name:
        return True  # nothing to check against
    text = f"{item.get('headline') or ''} {item.get('summary') or ''}"
    if re.search(rf"(?<![A-Za-z]){re.escape(ticker)}(?![A-Za-z])", text):
        return True
    words = [w for w in re.findall(r"[a-z0-9&']+", name.lower()) if w not in _NAME_FILLER]
    return bool(words) and re.search(rf"(?<![a-z0-9]){re.escape(words[0])}(?![a-z0-9])", text.lower()) is not None


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
                info = market.asset_info(c["ticker"])
                # a news-source tag must name the company in the story, whether Claude picked it or not: tags are
                # often foreign tickers that are a different US company (Dr. Martens "DOCS" is Doximity here; on
                # 2026-11-15 Claude kept Centrica's London tag "CNA", which is CNA Financial, an insurer, in the US)
                tagged = not c.get("direction") or c["ticker"] in it.get("_tags", [])
                if info and (not tagged or _names_company(info, c["ticker"], it)):
                    ok.append(c)
            except Exception:
                ok.append(c)  # lookup down: keep it rather than empty the card
        it["companies"] = ok
        it.pop("_tags", None)
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


KEEP_CURATED = int(os.getenv("MP_MOVERS_KEEP_CURATED_SECONDS", str(3 * 86400)))  # quiet weekend news
CARRY_HOURS = float(os.getenv("MP_MOVERS_CARRY_HOURS", "24"))


def _news_age_hours(item: dict) -> Optional[float]:
    try:
        t = datetime.fromisoformat(str(item.get("created_at") or "").replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).total_seconds() / 3600
    except ValueError:
        return None


def _carry(fresh: list[dict], old: list[dict]) -> list[dict]:
    """Each rebuild reads only the latest 30 headlines, so a quiet half hour of press releases left "Moving now"
    with one story (live 2026-11-17 10:24 AM ET: one Temu story, though the feed before it had more). Stories
    Claude already picked stay until they are CARRY_HOURS old, after the new ones; each card shows its own age."""
    out = list(fresh)
    seen = {it.get("headline") for it in out}
    for it in old or []:
        if len(out) >= MAX_ITEMS:
            break
        age = _news_age_hours(it)
        if it.get("headline") in seen or age is None or age > CARRY_HOURS or not it.get("companies"):
            continue
        # prices are re-read on every request; keep only what the story itself says
        out.append(dict(it, companies=[{k: c.get(k) for k in ("ticker", "direction", "why")} for c in it["companies"]]))
        seen.add(it.get("headline"))
    return out


ARCHIVE_KEY = "movers:archive"
ARCHIVE_DAYS = float(os.getenv("MP_MOVERS_ARCHIVE_DAYS", "7"))
ARCHIVE_MAX = 150  # ~11 picked stories a rebuild at most every 30 min; a week of distinct ones stays well under this


def archived() -> list[dict]:
    """Stories Claude picked for "Moving now" over the last ARCHIVE_DAYS, newest first (what News search reads)."""
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (ARCHIVE_KEY,))
    try:
        return list(json.loads(row["v"])) if row else []
    except Exception:
        return []


def _archive(items: list[dict]) -> None:
    """Keep each curated story (only what the story says; prices are re-read when shown) for News search."""
    try:
        old = archived()
        seen, out = set(), []
        for it in list(items) + old:
            h = it.get("headline")
            age = _news_age_hours(it)
            if not h or h in seen or not it.get("companies") or age is None or age > ARCHIVE_DAYS * 24:
                continue
            seen.add(h)
            out.append({k: it.get(k) or "" for k in ("headline", "source", "url", "created_at", "summary", "hunch", "why")}
                       | {"companies": [{k: c.get(k) for k in ("ticker", "direction", "why")} for c in it["companies"]]})
        out.sort(key=lambda it: str(it.get("created_at") or ""), reverse=True)
        db.execute("DELETE FROM kv_cache WHERE k = ?", (ARCHIVE_KEY,))
        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                   (ARCHIVE_KEY, json.dumps(out[:ARCHIVE_MAX]), datetime.now(timezone.utc).isoformat()))
    except Exception as e:  # search history is a nice-to-have; never break the feed over it
        log.warning("movers archive: %s", e)


def _age(feed: dict, key: str = "checked_at") -> float:
    """Seconds since the feed was last rebuilt or re-checked (key='built_at': since its stories were picked)."""
    try:
        return time.time() - datetime.fromisoformat(feed.get(key) or feed["built_at"]).timestamp()
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
                    if (not fresh.get("ai") and cur and cur.get("ai") and cur.get("items")
                            and _age(cur, "built_at") < KEEP_CURATED):
                        # Claude found nothing worth a hunch (or was down): keep the last curated feed, which says
                        # how old it is, rather than raw routine headlines (dividend dates, rating notes)
                        cur = dict(cur, checked_at=fresh["built_at"])
                        db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
                        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                                   (KEY, json.dumps(cur), fresh["built_at"]))
                    elif fresh["items"] or not (cur and cur.get("items")):
                        if fresh.get("ai") and cur and cur.get("ai"):
                            fresh["items"] = _carry(fresh["items"], cur.get("items") or [])
                        if fresh.get("ai"):
                            _archive(fresh["items"])
                        db.execute("DELETE FROM kv_cache WHERE k = ?", (KEY,))
                        db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                                   (KEY, json.dumps(fresh), fresh["built_at"]))
                        cur = fresh
                else:
                    cur = cur2
            finally:
                _lock.release()
    cur = dict(cur or {"items": [], "built_at": None, "ai": False})
    syms = sorted({c["ticker"] for it in cur["items"] for c in it["companies"]} | {BENCH})
    snaps = _snapshots(syms)
    bench = snaps.get(BENCH) or {}
    cur["benchmark"] = ({"ticker": BENCH, "change": bench["change"], "change_day": bench.get("change_day")}
                        if bench.get("change") is not None else None)
    cur["items"] = [dict(it, url=story_url(it.get("url"), [c["ticker"] for c in it["companies"]] + list(it.get("_tags") or [])),
                         companies=[_with_timing(_vs_market(dict(c, **snaps.get(c["ticker"], {})), bench),
                                                     it.get("created_at"))
                                        for c in it["companies"]])
                    for it in cur["items"]]
    cur["market"] = market.clock()
    return cur


# Some feeds (fiscal.ai summaries) attach one of their citations as the story's link, and it can be a quote page for
# an unrelated company: "Enphase Energy Reports Disappointing Revenue Guidance" linked to moomoo's O-I Glass (OI-US)
# page on 2026-11-23. A quote page for a ticker the story doesn't touch is dropped (the headline shows as plain text).
_QUOTE_PAGE = re.compile(r"/(?:stocks?|quotes?|symbols?)/([A-Za-z][A-Za-z.]{0,5})(?:-[A-Za-z]{2})?/?$", re.I)


def story_url(url: Any, tickers: list) -> str:
    """The story's link, or "" when it is a stock quote page for a company the story doesn't name."""
    u = str(url or "").strip()
    from urllib.parse import urlsplit
    try:
        path = urlsplit(u).path
    except ValueError:
        return ""
    m = _QUOTE_PAGE.search(path)
    if m and m.group(1).upper() not in {str(t).upper() for t in tickers or []}:
        return ""
    return u


BENCH = "SPY"  # the S&P 500, the same yardstick every grade in the app uses


def _vs_market(c: dict, bench: dict) -> dict:
    """Add vs_market: the stock's move minus the S&P 500's (SPY) over the same session, in fractions.

    A whole-market day moves almost every card the same way (live 2026-11-17: ACN "story helps" at -3.4%, MSFT
    -2.4%), so a bare "stock -3.4% today" can't tell the story's effect from the market's. Only set when both moves
    are from the same session; a stock's own ticker stays None (SPY vs itself is 0 by definition)."""
    ch, b = c.get("change"), (bench or {}).get("change")
    same_day = c.get("change_day") and c.get("change_day") == (bench or {}).get("change_day")
    c["vs_market"] = (round(ch - b, 4) if ch is not None and b is not None and same_day
                      and c.get("ticker") != BENCH else None)
    return c


def move_timing(created_at: Any, change_day: Any) -> Optional[str]:
    """Where the story falls against the session its price move is from (New York time, regular 9:30-4:00 hours).

    'before': the story came out after that session closed, so none of the move can be a reaction to it (live
    2026-11-18 2:50 AM ET: a Wed 7 AM story showed SERV "story helps" next to "-2.8% on Tue"). 'during': it came out
    mid-session, so part of the move came first. None: it came out before the session opened (the whole move is
    after it) or a time is missing. Early-close days are treated as a 4 PM close."""
    try:
        from zoneinfo import ZoneInfo
        t = datetime.fromisoformat(str(created_at or "").replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        d = date.fromisoformat(str(change_day or "")[:10])
    except ValueError:
        return None
    ny = ZoneInfo("America/New_York")
    opens = datetime(d.year, d.month, d.day, 9, 30, tzinfo=ny)
    closes = datetime(d.year, d.month, d.day, 16, 0, tzinfo=ny)
    if t >= closes:
        return "before"
    if t > opens:
        return "during"
    return None


def _with_timing(c: dict, created_at: Any) -> dict:
    """Add move_timing (see move_timing) to a company that has a price move."""
    c["move_timing"] = move_timing(created_at, c.get("change_day")) if c.get("change") is not None else None
    return c


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
  Never a bare date or year: it would read like today's date.
- hook_line: one sentence under 14 words that makes someone want to keep reading. Stay neutral: report who
  reacted, never judge whose opinion matters or take a political side.
- happened: what happened, in at most 30 words.
- figures: 0 to 2 before/after comparisons, ONLY when both numbers are written in the headline or summary
  ("Cloud sales": "A year ago" "$15.2B" -> "Now" "$30.7B"; or "What Wall Street expected" vs "Actual").
  Copy the numbers exactly as written. Never estimate, round or invent a number. If unsure, return [].
- why: why it matters for companies and investors, as a short chain of cause and effect, at most 30 words, in
  whole sentences.
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


_SENT_END = re.compile(r"(?<=[a-z0-9%)\"'’])[.!?](?=\s+[A-Z\"“]|$)")


def _sentences(s: Any, n: int) -> str:
    """Story text cut at the last whole sentence that fits, so a card never stops mid-thought ("which may matter
    for housing-linked…"). Only when no whole sentence fits is it clipped at a word with "…". Also mends text
    cached before this rule (it ends in "…" with a whole sentence before it)."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) <= n and not s.endswith("…"):
        return s
    body = s.rstrip("…").rstrip()
    ends = [m.end() for m in _SENT_END.finditer(body[:n])]
    if ends and ends[-1] >= 25:
        return body[: ends[-1]]
    return s if len(s) <= n else _clip(s, n)


_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
_BARE_DATE = re.compile(rf"^(?:on\s+)?(?:(?P<m1>(?:{_MONTHS})[a-z]*)\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?"
                        rf"|(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<m2>(?:{_MONTHS})[a-z]*)\.?)(?:,?\s+(?P<y>\d{{4}}))?$", re.I)


_BARE_YEAR = re.compile(r"^(?:in\s+|by\s+)?(?:19|20)\d\d[.!]?$", re.I)


def _undate(s: str) -> str:
    """A bare date as the hook ("November 30, 2026") sits under "Moving now" and reads like the page's own date
    (a future one, if the article is about a launch). Say it as when the news is for: "On Nov 30" (year kept only
    when it isn't this year)."""
    m = _BARE_DATE.match(s)
    if not m:
        return s
    mon = (m.group("m1") or m.group("m2"))[:3].title()
    day = int(m.group("d1") or m.group("d2"))
    y = m.group("y")
    out = f"On {mon} {day}"
    return out + (f", {y}" if y and int(y) != datetime.now(timezone.utc).year else "")


_HEDGES = ("up to", "as much as", "as many as", "more than", "less than", "at least", "nearly", "almost", "about",
           "around", "roughly", "approximately", "an estimated", "over", "under")
_HEDGE_RE = "|".join(re.escape(h) for h in _HEDGES)
# Words that make a number a possibility, not a fact, when they sit a few words before it ("potentially valued at",
# "could be worth", "may reach").
_SOFT_RE = r"[Pp]otentially|[Pp]ossibly|could|may|might"  # case-sensitive: "May" the month is not a hedge
_SOFT_IN_HOOK = r"\b(?:potential(?:ly)?|possibl[ey]|could|may|might|proposed|reported(?:ly)?|eyes|talks?)\b"


# Words that make a number a company's or analyst's forecast, not a result, when they come earlier in its sentence
# ("Mission Produce Projects 10% Increase", "it expects volumes to rise by approximately 10%").
_FORECAST_RE = r"\b(?:project(?:s|ed|ing|ions?)?|forecast(?:s|ed|ing)?|expect(?:s|ed|ing|ations?)?|predict(?:s|ed|ing)?|guid(?:es|ed|ance)|outlook|anticipat\w*)\b"
_FORECAST_IN_HOOK = _FORECAST_RE + r"|\b(?:set to|on track|could|may|might|potential(?:ly)?|plans?|aims?|targets?|estimated?)\b"
_NOT_A_NOUN = {"in", "on", "at", "since", "from", "for", "over", "after", "before", "this", "last", "a", "an", "the", "to",
               "than", "by", "and", "or", "year", "years", "week", "weeks", "day", "days", "month", "months", "quarter",
               "yoy", "ytd", "y/y", "again", "more", "today"}


def _reordered(s: str) -> str:
    """"Up 10% supply" (live 2026-11-22, Story hook) reads like a typo; say it the plain way: "Supply up 10%".
    Only when what follows the number is a short noun phrase ("Up 10% in a week" stays as it is)."""
    m = re.match(r"^(Up|Down)\s+(\$?\d[\d,]*(?:\.\d+)?%?)\s+([A-Za-z][\w'-]*(?:\s+[A-Za-z][\w'-]*){0,2})$", s)
    if not m or any(w.lower() in _NOT_A_NOUN for w in m.group(3).split()):
        return s
    rest = m.group(3)
    rest = rest[0].upper() + rest[1:]
    return f"{rest} {m.group(1).lower()} {m.group(2)}"


def _forecast(s: str, source: str) -> str:
    """A number the article only gives as a forecast ("projects", "expects", "guidance") gets "Forecast:" on the hook,
    so the giant hook doesn't read like a result. Live 2026-11-22: "Up 10% supply" for "Mission Produce Projects 10%
    Increase in Avocado Industry Volumes" (the summary: "it expects ... to rise by approximately 10%")."""
    if not s or not source or re.search(_FORECAST_IN_HOOK, s, re.I):
        return s
    for m in re.finditer(r"\$?\d[\d,]*(?:\.\d+)?", s):
        num = m.group()
        if _BARE_YEAR.match(num):
            continue
        pat = rf"(?<![\w$.,]){re.escape(num)}(?![\d]|[.,]\d)"
        uses = list(re.finditer(pat, source))
        if not uses:
            continue
        sentences = [re.split(r"[.;!?\n]\s", source[: u.start()])[-1] for u in uses]
        if all(re.search(_FORECAST_RE, x, re.I) for x in sentences):
            return f"Forecast: {s}"
    return s


def _hedged(s: str, source: str) -> str:
    """Keep the article's hedge on a hook's number. Live 2026-11-21: the article said Saudi Arabia will supply "up to
    8 million barrels" and the giant hook read "8 million barrels", a firmer claim than the news. If the article only
    writes the number after a hedge ("up to", "about", "more than", ...) and the hook drops it, put it back."""
    if not s or not source:
        return s
    out = s
    for m in reversed(list(re.finditer(r"\$?\d[\d,]*(?:\.\d+)?", s))):
        num = m.group()
        before = s[: m.start()].lower()
        if re.search(rf"(?:{_HEDGE_RE})\s*$", before):
            continue  # the hook kept the hedge
        pat = rf"(?<![\w$.,]){re.escape(num)}(?![\d]|[.,]\d)"
        uses = list(re.finditer(pat, source))
        if not uses:
            continue
        hedges = [re.search(rf"\b({_HEDGE_RE})\s+$", source[: u.start()], re.I) for u in uses]
        if all(hedges):  # every mention is hedged: the bare number overstates it
            h = hedges[0].group(1).lower()
            out = out[: m.start()] + (h.capitalize() if m.start() == 0 else h) + " " + out[m.start():]
            continue
        # A softer hedge a few words back: live 2026-11-22 the article said "a deal potentially valued at $45 billion"
        # and the giant hook read "$45 billion", as if the deal's size were settled.
        if re.search(_SOFT_IN_HOOK, s, re.I):
            continue  # the hook already says it may not happen ("A potential $45 billion deal")
        soft = [re.search(rf"\b({_SOFT_RE})\b(?:\s+[\w-]+){{0,3}}\s+$", source[: u.start()]) for u in uses]
        if all(soft):
            h = "possibly" if soft[0].group(1).lower() == "possibly" else "potentially"
            out = out[: m.start()] + (h.capitalize() if m.start() == 0 else h) + " " + out[m.start():]
    return out


def _hook(s: Any, source: str = "") -> str:
    """The big hook phrase, whole or not at all: clipping it can flip its meaning
    ("Credit stress looks contained" -> "Credit stress looks…"). With the article's text, a number the article
    hedges ("up to 8 million") keeps its hedge, or the hook is dropped if that makes it too long."""
    s = _undate(re.sub(r"\s+", " ", str(s or "")).strip())
    s = _forecast(_hedged(_reordered(s), source), source)
    whole = not s.endswith(("…", "..."))  # a hook cut by an older rule ("11,000 satellites, still…")
    if _BARE_YEAR.match(s):  # live 2026-11-17: "2026" (a conference's year) as the giant hook under "Moving now"
        return ""
    return s if s and whole and len(s) <= 40 and len(s.split()) <= 5 else ""


def _fallback_story(item: dict) -> dict:
    nums = [n for n in re.findall(r"(?<![A-Za-z\d-])[$]?\d[\d,.]*\s?(?:%|billion|million|trillion|B|M)?(?![A-Za-z\d-])", item["headline"])
            if not _BARE_YEAR.match(n.strip())]  # "2026 Dubai Precious Metals Conference": a year isn't a hook
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
    return {"hook_big": _hook(d.get("hook_big"), source) or _fallback_story(item)["hook_big"], "hook_line": _clip(d.get("hook_line"), 120),
            "happened": _sentences(d.get("happened"), 320), "figures": figs[:2], "why": _sentences(d.get("why"), 240),
            "twist": _sentences(d.get("twist"), 200), "ai": True}


def story(headline: str, client: Any = None) -> Optional[dict]:
    """The story for one headline in today's feed or this week's archive (None otherwise: no arbitrary prompts)."""
    headline = (headline or "").strip()
    if not headline:
        return None
    cur = feed(client)
    item = next((it for it in cur.get("items", []) if it["headline"] == headline), None)
    if not item:  # a story from earlier this week, found through News search (still one Claude picked)
        item = next((it for it in archived() if it.get("headline") == headline), None)
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
    if st.get("hook_big"):  # stories cached before the date rule
        st["hook_big"] = _hook(st["hook_big"], f"{item['headline']}\n{item.get('summary') or ''}") or _fallback_story(item)["hook_big"]
    if st.get("ai"):  # stories cached before the whole-sentence rule
        for k, n in (("happened", 320), ("why", 240), ("twist", 200)):
            if st.get(k):
                st[k] = _sentences(st[k], n)
    return {"story": st, "item": item, "market": cur.get("market")}
