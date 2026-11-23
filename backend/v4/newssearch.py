"""
News search: find stories about something specific (a company, a ticker or a topic) on the News page.

Reads only what the app already has: this week's "Moving now" stories (today's feed plus movers.archived()), and,
when the search names a company, that company's latest headlines from the same news source. No Claude call, so a
search costs nothing and can't be used to prompt the model.
"""
from __future__ import annotations

import difflib
import re
import threading
import time
from typing import Any, Optional

from . import market, movers

MAX_STORIES = 10
MAX_HEADLINES = 6
_TICKERISH = re.compile(r"^\$?[A-Za-z][A-Za-z.]{0,5}$")
_STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "for", "to", "about", "news", "stock", "stocks", "shares",
         "inc", "corp", "company", "is", "are", "what", "whats", "with",
         # question and filler words, so a sentence searches its subject: "why is nvidia up?" -> nvidia,
         # "what happened to oil" -> oil, "is tesla a buy" -> tesla
         "what's", "why", "how", "who", "when", "where", "which", "happened", "happening", "happen", "going",
         "does", "did", "do", "doing", "will", "would", "should", "could", "can", "up", "down", "today", "today's",
         "this", "that", "week", "it", "its", "it's", "i", "me", "my", "we", "our", "you", "buy", "sell", "worth",
         "good", "bad", "there", "was", "were", "be", "been", "has", "have", "had", "so", "much", "right", "now",
         "price", "prices", "moving", "move", "moved", "rise", "rising", "fall", "falling", "latest", "tell"}
# All-caps words in a sentence that are words, not the tickers they happen to be ("why is AI hot" isn't C3.ai)
_CAPS_WORDS = {"AI", "US", "USA", "CEO", "CFO", "IPO", "ETF", "EV", "EVS", "GDP", "FED", "OK", "UK", "EU", "IT", "I",
               "A", "IS", "ON", "TV", "AM", "PM", "Q1", "Q2", "Q3", "Q4", "CPI", "SEC", "FDA", "WHY", "HOW", "WHAT"}
# Well-known companies people search by name even when no story this week moves them ("apple" -> AAPL). Only
# names that aren't everyday topic words, so "gold" or "oil" still search the stories as topics.
_KNOWN = {"apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT", "amazon": "AMZN", "google": "GOOGL",
          "alphabet": "GOOGL", "meta": "META", "facebook": "META", "netflix": "NFLX", "nvidia": "NVDA",
          "palantir": "PLTR", "intel": "INTC", "disney": "DIS", "walmart": "WMT", "costco": "COST", "nike": "NKE",
          "boeing": "BA", "coca cola": "KO", "coca-cola": "KO", "pepsi": "PEP", "pepsico": "PEP",
          "mcdonalds": "MCD", "mcdonald's": "MCD", "starbucks": "SBUX", "jpmorgan": "JPM", "exxon": "XOM",
          "chevron": "CVX", "pfizer": "PFE", "uber": "UBER", "airbnb": "ABNB", "spotify": "SPOT",
          "salesforce": "CRM", "oracle": "ORCL", "broadcom": "AVGO", "adobe": "ADBE", "paypal": "PYPL",
          "ford": "F", "berkshire": "BRK.B", "coinbase": "COIN", "robinhood": "HOOD", "amd": "AMD",
          # the big indexes, shown as the ETF that tracks them ("nasdaq" alone stays Nasdaq, Inc.; "dow" is Dow Inc.)
          "s&p 500": "SPY", "s&p": "SPY", "s&p500": "SPY", "sp500": "SPY", "sp 500": "SPY",
          "dow jones": "DIA", "nasdaq 100": "QQQ", "nasdaq-100": "QQQ", "russell 2000": "IWM"}
# lowercase tickers of the well-known names above that are also everyday words: "cost" or "spot" typed alone may be
# the word, so those still read "in case you meant the company"; "aapl" or "tsla" never mean anything else
_TICKER_WORDS = {"cost", "spot", "coin", "hood", "dis", "pep", "ko", "ba", "f", "spy", "dia"}
_lock = threading.Lock()
_news_cache: dict[str, tuple[float, list[dict]]] = {}


def _words(s: Any) -> list[str]:
    return re.findall(r"[a-z0-9&']+", str(s or "").lower())


def terms(q: str) -> list[str]:
    """The words a search must find ("nvidia news" -> ["nvidia"]); a search of only filler words keeps them."""
    ws = _words(q)
    kept = [w for w in ws if w not in _STOP]
    return kept or ws


def _story_text(it: dict) -> list[str]:
    parts = [it.get("headline"), it.get("summary"), it.get("hunch"), it.get("why")]
    parts += [c.get("why") for c in it.get("companies") or []]
    return _words(" ".join(str(p or "") for p in parts))


def _matches(it: dict, ts: list[str], ticker: Optional[str], exact: bool = False) -> int:
    """0 = no match. Otherwise a rank: 3 the story moves the searched company, 2 every word in the headline,
    1 every word somewhere in the story. A word matches the start of a story word ("chip" finds "chipmaker"), or
    the whole word when exact (a ticker search: "DIA" mustn't find "diagnostic")."""
    tickers = {str(c.get("ticker") or "").upper() for c in it.get("companies") or []}
    if ticker and ticker in tickers:
        return 3
    if not ts:
        return 0
    if len(ts) == 1 and ts[0].upper() in tickers:
        return 3
    hit = (lambda w, t: w == t) if exact else (lambda w, t: w.startswith(t))
    head = _words(it.get("headline"))
    if all(any(hit(w, t) for w in head) for t in ts):
        return 2
    body = _story_text(it)
    return 1 if all(any(hit(w, t) for w in body) for t in ts) else 0


def _company(q: str, stories: list[dict], topic_hits: bool = False) -> Optional[dict]:
    """The company the search names: a ticker typed as one ("NVDA", "$nvda", or "nvda" when it's a ticker in this
    week's stories or no story uses the word), or a company whose name starts with the search ("nvidia") among the
    companies this week's stories move, or a well-known name in _KNOWN ("apple"). A lowercase word that no story
    uses but is a ticker ("gold" is Gold.com's GOLD) comes back with guess=True, so the page says it found no
    stories about the word and is showing the stock with that ticker instead."""
    raw = q.strip()
    pool_syms = {str(c.get("ticker") or "").upper() for it in stories for c in it.get("companies") or []}
    known = _KNOWN.get(" ".join(terms(q))) or _KNOWN.get(raw.lower())
    if known:
        try:
            info = market.asset_info(known)
        except Exception:
            info = None
        if info:
            return {"ticker": info["symbol"], "name": info.get("name") or ""}
    if _TICKERISH.match(raw) and (raw.startswith("$") or raw.isupper() or raw.upper() in pool_syms
                                  or (len(raw) <= 5 and not topic_hits)):
        sym = raw.lstrip("$").upper()
        try:
            info = market.asset_info(sym)
        except Exception:
            info = None
        if info:
            out = {"ticker": info["symbol"], "name": info.get("name") or ""}
            # a lowercase word no story uses ("gold", "car") may be a topic that happens to be a ticker: say so
            if not (raw.startswith("$") or raw.isupper() or raw.upper() in pool_syms
                    or (sym in _KNOWN.values() and raw.lower() not in _TICKER_WORDS)):
                out["guess"] = True
            return out
    ts = terms(q)
    if not ts:
        return None
    seen: set[str] = set()
    for it in stories:
        for c in it.get("companies") or []:
            sym = str(c.get("ticker") or "").upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            try:
                info = market.asset_info(sym)
            except Exception:
                info = None
            name = [w for w in _words((info or {}).get("name")) if w not in movers._NAME_FILLER]
            if name and name[:len(ts)] == ts:
                return {"ticker": sym, "name": info.get("name") or ""}
    # a well-known name anywhere in a longer search: "costco earnings", "earnings from costco" -> COST
    grams = [" ".join(ts[i:i + n]) for n in (2, 1) for i in range(len(ts) - n + 1)]
    # or a ticker typed in capitals inside a sentence: "why is TSLA up?", "$nvda after earnings"
    raw_ws = raw.replace("?", " ").replace(",", " ").split()
    caps = [w.lstrip("$").upper() for w in raw_ws if len(raw_ws) > 1 and re.fullmatch(r"\$[A-Za-z]{1,5}|[A-Z]{2,5}", w)
            and (w.startswith("$") or w not in _CAPS_WORDS)]
    for sym in [_KNOWN[g] for g in grams if g in _KNOWN] + caps:
        try:
            info = market.asset_info(sym)
        except Exception:
            info = None
        if info:
            return {"ticker": info["symbol"], "name": info.get("name") or ""}
    return None


def _vocab(stories: list[dict]) -> set[str]:
    """Words a search could have meant: this week's story words, the names of the companies they move, and the
    well-known names in _KNOWN. Only words of 4+ letters, so short words are never "corrected"."""
    out = {w for k in _KNOWN for w in _words(k)}
    for it in stories:
        out.update(_story_text(it))
        for c in it.get("companies") or []:
            sym = str(c.get("ticker") or "").upper()
            try:  # already looked up (and cached) by _company for every company in the pool
                info = market.asset_info(sym) if sym else None
            except Exception:
                info = None
            out.update(_words((info or {}).get("name")))
    return {w for w in out if len(w) >= 4 and w.isalpha()}


def suggest(q: str, stories: list[dict]) -> Optional[str]:
    """A likely spelling for a search that found nothing ("nvdia" -> "nvidia", "teslla" -> "tesla", "lithum" ->
    "lithium"), or None. A word is only changed when no known word starts with it and a known word is a close
    match (difflib ratio >= 0.8, same first letter), so real words the app has no story about ("uranium") are left alone."""
    ts = terms(q.lstrip("$"))
    if not ts:
        return None
    whole = " ".join(ts)
    if len(whole) >= 4 and whole not in _KNOWN:
        m = difflib.get_close_matches(whole, [k for k in _KNOWN if k[0] == whole[0]], n=1, cutoff=0.8)
        if m:
            return m[0]
    vocab = _vocab(stories)
    out, changed = [], False
    for t in ts:
        if len(t) < 4 or not t.isalpha() or any(w.startswith(t) for w in vocab):
            out.append(t)
            continue
        m = difflib.get_close_matches(t, sorted(w for w in vocab if w[0] == t[0]), n=1, cutoff=0.8)
        out.append(m[0] if m else t)
        changed = changed or bool(m)
    return " ".join(out) if changed else None


def _names_fund(sym: str, text: str) -> bool:
    """The headline names the fund: its ticker as a word, or ETF. (Not the summary: Questcorp's says "CSE: QQQ".)"""
    return bool(re.search(rf"(?<![A-Za-z]){re.escape(sym)}(?![A-Za-z])", text) or re.search(r"\bETFs?\b", text))


def headlines_for(sym: str) -> list[dict]:
    """The company's latest headlines from the news source, cached 20 minutes per ticker. [] when unavailable."""
    now = time.time()
    with _lock:
        hit = _news_cache.get(sym)
        if hit and now - hit[0] < 1200:
            return hit[1]
    try:
        r = market._session.get(f"{market._data_base()}/v1beta1/news", headers=market._headers(),
                                params={"symbols": sym, "limit": 12, "sort": "desc", "include_content": "false"},
                                timeout=8)
        raw = r.json().get("news", []) if r.status_code == 200 else []
    except Exception:
        return []
    try:
        fund = bool((market.asset_info(sym) or {}).get("is_etf"))
    except Exception:
        fund = False
    out, seen = [], set()
    for n in raw:
        h = (n.get("headline") or "").strip()
        if not h or h.lower()[:60] in seen or len(h) > 200:
            continue
        # the news source tags foreign listings that share a fund's letters (QQQ: Questcorp Mining, DIA: DiaSorin,
        # GLD: Gold Finder), so a fund's headline counts only if it names the fund's ticker or says ETF
        if fund and not _names_fund(sym, h):
            continue
        seen.add(h.lower()[:60])
        out.append({"headline": h, "source": n.get("source") or "", "url": movers.story_url(n.get("url"), [sym] + list(n.get("symbols") or [])),
                    "created_at": n.get("created_at") or ""})
        if len(out) == MAX_HEADLINES:
            break
    with _lock:
        if len(_news_cache) > 300:
            _news_cache.clear()
        _news_cache[sym] = (now, out)
    return out


def search(q: str, fix: bool = True) -> dict:
    """Stories and the named company for a search. fix=False searches exactly as typed (no spelling fix)."""
    q = re.sub(r"\s+", " ", str(q or "")).strip()[:60]
    if len(q.lstrip("$")) < 2:
        return {"q": q, "company": None, "stories": [], "headlines": [], "days": movers.ARCHIVE_DAYS}
    cur = movers.feed()
    seen, pool = set(), []
    for it in list(cur.get("items") or []) + movers.archived():
        if it.get("headline") and it["headline"] not in seen:
            seen.add(it["headline"])
            pool.append(it)
    out = _search(q, pool, cur)
    if fix and not out["stories"] and not out["company"]:
        # nothing at all: try the likely spelling ("nvdia" -> "nvidia") and say so on the page
        fix = suggest(q, pool)
        if fix and fix != q.lower():
            alt = _search(fix, pool, cur)
            if alt["stories"] or alt["company"]:
                alt["corrected_from"] = q
                return alt
    return out


def _search(q: str, pool: list[dict], cur: dict) -> dict:
    ts = terms(q)
    company = _company(q, pool, topic_hits=any(_matches(it, ts, None) for it in pool))
    # the search is the ticker itself ("DIA", "$qqq"): its letters must be a whole word, not the start of one
    exact = bool(company) and ts == [company["ticker"].lower()]
    ranked = [(r, i, it) for i, it in enumerate(pool) if (r := _matches(it, ts, company and company["ticker"], exact))]
    ranked.sort(key=lambda x: (-x[0], -_ts(x[2]), x[1]))
    stories = [it for _, _, it in ranked[:MAX_STORIES]]
    # today's prices, the same way the feed shows them (feed items already carry them)
    syms = sorted({c["ticker"] for it in stories for c in it["companies"] if "change" not in c}
                  | ({company["ticker"]} if company else set()) | {movers.BENCH})
    snaps = movers._snapshots(syms)
    bench = snaps.get(movers.BENCH) or {}
    stories = [it if all("change" in c for c in it["companies"]) else
               dict(it, companies=[movers._with_timing(movers._vs_market(dict(c, **snaps.get(c["ticker"], {})), bench),
                                                       it.get("created_at")) for c in it["companies"]])
               for it in stories]
    stories = [dict(it, url=movers.story_url(it.get("url"), [c["ticker"] for c in it["companies"]] + list(it.get("_tags") or [])))
               for it in stories]
    heads: list[dict] = []
    if company:
        company = movers._vs_market(dict(company, **snaps.get(company["ticker"], {})), bench)
        shown = {it["headline"].lower()[:60] for it in stories}
        heads = [h for h in headlines_for(company["ticker"]) if h["headline"].lower()[:60] not in shown]
    return {"q": q, "company": company, "stories": stories, "headlines": heads, "days": movers.ARCHIVE_DAYS,
            "benchmark": cur.get("benchmark")}


def _ts(it: dict) -> float:
    age = movers._news_age_hours(it)
    return -age if age is not None else -1e9
