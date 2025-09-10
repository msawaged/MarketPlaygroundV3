# backend/news_ingestor.py
"""
News Ingestor (single-cycle)
- Reads NEWS_SOURCES (comma-separated URLs or JSON array).
- Pulls Alpaca news when configured via "alpaca:SYMB1|SYMB2|...".
- Optionally calls your local news_scraper.py if present, to merge custom items.
- Dedupe + atomic append to data/news_beliefs.csv.
- Writes backend/news_ingestor_metrics.json (atomic).
- Safe on errors; structured, timestamped stdout logs.
- Run mode: one cycle only (loop handled by news_ingestor_loop.py).
"""

import csv
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from dotenv import load_dotenv
load_dotenv()

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log(msg: str):
    ts = _utc_now_iso()
    print(f"[{ts}] [news_ingestor] {msg}")

# Optional deps — keep import failures non-fatal for dev
try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    import feedparser  # RSS/Atom
except Exception:  # pragma: no cover
    feedparser = None

# Optional custom scraper module (yours). If present, we can call it.
CUSTOM_SCRAPER_FUNCS = []
try:
    # Prefer absolute import when running from repo root
    from backend import news_scraper as custom_scraper  # type: ignore
    # Examine common function names
    for candidate in ("get_custom_news", "scrape_news", "get_news", "scrape"):
        if hasattr(custom_scraper, candidate) and callable(getattr(custom_scraper, candidate)):
            CUSTOM_SCRAPER_FUNCS.append(getattr(custom_scraper, candidate))
except Exception:
    # No custom scraper: that's okay
    custom_scraper = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
# Canonical data dir at repo root (aligns with hot_trades_router.py)
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = DATA_DIR / "news_beliefs.csv"
METRICS_JSON = BASE_DIR / "news_ingestor_metrics.json"
STATE_JSON = BASE_DIR / "news_ingestor_state.json"  # persistent dedupe/last-run

_log(f"INIT REPO_ROOT: {REPO_ROOT}")
_log(f"INIT TARGET CSV PATH: {OUT_CSV.resolve()}")


ALPACA_DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")
print("[news_ingestor] INIT ALPACA_NEWS_ENABLED:", os.getenv("ALPACA_NEWS_ENABLED"))
print("[news_ingestor] INIT NEWS_SOURCES:", os.getenv("NEWS_SOURCES"))

def _csv_header() -> List[str]:
    return ["timestamp_utc", "story_id", "title", "url", "source", "summary", "tickers"]

def _ensure_csv():
    if not OUT_CSV.exists():
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(_csv_header())

def _atomic_write_json(path: Path, data: Dict):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _write_metrics(data: Dict):
    _atomic_write_json(METRICS_JSON, data)

def _atomic_write_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)

def _load_state() -> Dict:
    if STATE_JSON.exists():
        try:
            return json.loads(STATE_JSON.read_text())
        except Exception:
            pass
    return {"seen_ids": [], "last_run_utc": None}

def _save_state(state: Dict):
    _atomic_write_text(STATE_JSON, json.dumps(state, indent=2))

def _load_seen_ids() -> set:
    st = _load_state()
    return set(st.get("seen_ids", []))

def _remember_ids(new_ids: Iterable[str]):
    st = _load_state()
    seen = set(st.get("seen_ids", []))
    for i in new_ids:
        if i:
            seen.add(i)
    st["seen_ids"] = list(seen)[-100000:]  # cap memory
    st["last_run_utc"] = _utc_now_iso()
    _save_state(st)

def _parse_sources_env() -> List[str]:
    raw = os.getenv("NEWS_SOURCES", "").strip()
    if not raw:
        raw = "https://www.marketwatch.com/rss/topstories,https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
    if not raw:
        return []
    # Allow JSON array or comma-separated
    if (raw.startswith("[") and raw.endswith("]")) or (raw.startswith("{") and raw.endswith("}")):
        try:
            obj = json.loads(raw)
            if isinstance(obj, list):
                return [str(x).strip() for x in obj if str(x).strip()]
            return []
        except Exception:
            return []
    # Comma-separated
    return [s.strip() for s in raw.split(",") if s.strip()]

# === Fetchers ===

def _normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _fetch_rss(url: str, timeout: int = 10) -> List[Dict]:
    if feedparser is None:
        _log("WARNING: feedparser not installed; skipping RSS/Atom source.")
        return []
    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        _log(f"ERROR fetching RSS {url}: {e}")
        return []
    out = []
    for e in parsed.entries:
        story_id = e.get("id") or e.get("guid") or e.get("link") or e.get("title")
        out.append({
            "story_id": str(story_id) if story_id else None,
            "title": e.get("title") or "",
            "url": e.get("link") or "",
            "source": url,
            "summary": e.get("summary") or e.get("description") or "",
            "tickers": [],  # optional enrichment later
        })
    return out

def _fetch_http_json(url: str, timeout: int = 10) -> List[Dict]:
    if requests is None:
        _log("WARNING: requests not installed; skipping JSON source.")
        return []
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        _log(f"ERROR fetching JSON {url}: {e}")
        return []
    out = []
    if isinstance(data, dict) and "items" in data and isinstance(data["items"], list):
        items = data["items"]
    elif isinstance(data, list):
        items = data
    else:
        items = []
    for it in items:
        story_id = it.get("id") or it.get("uuid") or it.get("url")
        out.append({
            "story_id": str(story_id) if story_id else None,
            "title": it.get("title") or "",
            "url": it.get("url") or "",
            "source": url,
            "summary": _normalize_text(it.get("summary") or it.get("description") or ""),
            "tickers": it.get("tickers") or it.get("symbols") or [],
        })
    return out

def _fetch_alpaca_news(symbols: List[str], limit: int = 25) -> List[Dict]:
    if requests is None:
        _log("WARNING: requests not installed; skipping Alpaca.")
        return []
    if not ALPACA_API_KEY or not ALPACA_API_SECRET:
        _log("INFO: Alpaca credentials not set; skipping Alpaca news.")
        return []
    url = f"{ALPACA_DATA_BASE}/v1beta1/news"
    try:
        params = {"symbols": ",".join(symbols), "limit": str(limit)}
        headers = {
            "Apca-Api-Key-Id": ALPACA_API_KEY,
            "Apca-Api-Secret-Key": ALPACA_API_SECRET,
        }
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        _log(f"ERROR fetching Alpaca news: {e}")
        return []
    items = data.get("news", []) if isinstance(data, dict) else []
    out = []
    for it in items:
        story_id = it.get("id") or it.get("uuid") or it.get("url")
        title = it.get("headline") or it.get("title") or ""
        url_item = it.get("url") or ""
        summary = it.get("summary") or ""
        syms = it.get("symbols") if isinstance(it.get("symbols"), list) else []
        out.append({
            "story_id": str(story_id) if story_id else None,
            "title": title,
            "url": url_item,
            "source": "alpaca",
            "summary": summary,
            "tickers": syms or [],
        })
    return out

def _infer_fetcher(entry: str) -> Tuple[str, Dict]:
    """
    Recognizes:
      - "alpaca:SYMB1|SYMB2|..." -> Alpaca news for symbols
      - http(s)://...           -> RSS/Atom (via feedparser) OR JSON (fallback)
      - feed://...              -> treat like RSS
    """
    if entry.startswith("alpaca:"):
        symbols = [s for s in entry.split(":", 1)[1].split("|") if s]
        return ("alpaca", {"symbols": symbols})
    if entry.startswith("feed://"):
        url = "http://" + entry[len("feed://"):]
        return ("rss", {"url": url})
    if entry.startswith("http://") or entry.startswith("https://"):
        # Try RSS via feedparser first, fall back to JSON fetch if looks JSON
        return ("rss", {"url": entry})
    return ("unknown", {})

def _collect_sources() -> List[Dict]:
    entries = _parse_sources_env()
    if not entries:
        _log("INFO: NEWS_SOURCES is empty and no custom scraper detected; nothing to ingest.")
        return []
    out = []
    for entry in entries:
        kind, params = _infer_fetcher(entry)
        if kind == "alpaca" and params.get("symbols"):
            out.append({"kind": "alpaca", "params": params})
        elif kind == "rss":
            out.append({"kind": "rss", "params": params})
        elif kind == "unknown" and entry:
            # Try JSON anyway
            out.append({"kind": "json", "params": {"url": entry}})
    return out

def _atomic_append_rows(rows: List[List[str]]):
    """Atomic append: read current -> write merged tmp -> replace."""
    _ensure_csv()
    with OUT_CSV.open("r", newline="", encoding="utf-8") as rf:
        existing = rf.read()

    with tempfile.NamedTemporaryFile("w", delete=False, newline="", encoding="utf-8") as tf:
        tf.write(existing)
        w = csv.writer(tf)
        for row in rows:
            w.writerow(row)
        tmp_path = Path(tf.name)

    tmp_path.replace(OUT_CSV)

def main() -> int:
    start_ts = datetime.now(timezone.utc).timestamp()

    sources = _collect_sources()
    if not sources:
        _write_metrics({
            "polled_feeds": 0,
            "fetched": 0,
            "new_written": 0,
            "duration_seconds": 0.0,
            "alpaca_enabled": bool(ALPACA_API_KEY and ALPACA_API_SECRET),
            "custom_scraper": bool(CUSTOM_SCRAPER_FUNCS),
        })
        return 0

    # Seed CSV header if needed
    _ensure_csv()

    collected: List[Dict] = []
    fetched = 0

    # RSS / JSON / Alpaca fetch
    for s in sources:
        if s["kind"] == "alpaca":
            syms = s["params"].get("symbols") or []
            items = _fetch_alpaca_news(syms)
            fetched += len(items)
            collected.extend(items)
        elif s["kind"] == "rss":
            url = s["params"]["url"]
            items = _fetch_rss(url)
            fetched += len(items)
            collected.extend(items)
        elif s["kind"] == "json":
            url = s["params"]["url"]
            items = _fetch_http_json(url)
            fetched += len(items)
            collected.extend(items)

    # Custom scraper (optional)
    if CUSTOM_SCRAPER_FUNCS:
        total_custom = 0
        for func in CUSTOM_SCRAPER_FUNCS:
            try:
                custom_items = func()  # must return iterable of dicts
            except TypeError:
                # if function expects no args but we passed none (or vice versa), attempt calling with no args
                custom_items = func()
            except Exception as e:
                _log(f"WARNING: custom scraper {func.__name__} failed: {e}")
                continue

            mapped = []
            for it in (custom_items or []):
                # Map arbitrary dicts into our schema (best-effort)
                story_id = it.get("story_id") or it.get("id") or it.get("uuid") or it.get("url") or it.get("title")
                mapped.append({
                    "story_id": str(story_id) if story_id else None,
                    "title": it.get("title", ""),
                    "url": it.get("url", ""),
                    "source": it.get("source", "custom_scraper"),
                    "summary": it.get("summary", "") or it.get("description", ""),
                    "tickers": it.get("tickers", []) or it.get("symbols", []),
                })
            total_custom += len(mapped)
            collected.extend(mapped)
        _log(f"Custom scraper contributed {total_custom} items")

    # normalize fields
    for it in collected:
        it["story_id"] = (it.get("story_id") or "").strip()
        it["title"] = _normalize_text(it.get("title"))
        it["url"] = (it.get("url") or "").strip()
        it["source"] = (it.get("source") or "").strip()
        it["summary"] = _normalize_text(it.get("summary"))
        syms = it.get("tickers") or []
        if isinstance(syms, str):
            syms = [s.strip().upper() for s in syms.split(",") if s.strip()]
        if isinstance(syms, list):
            syms = [str(s).strip().upper() for s in syms if str(s).strip()]
        it["tickers"] = syms

    seen = _load_seen_ids()
    new_rows: List[List[str]] = []
    newly_seen: List[str] = []

    for it in collected:
        sid = it.get("story_id") or it.get("url") or ""
        if not sid:
            continue
        if sid in seen:
            continue

        newly_seen.append(sid)
        row = [
            _utc_now_iso(),
            sid,
            it.get("title", ""),
            it.get("url", ""),
            it.get("source", ""),
            it.get("summary", ""),
            ";".join(it.get("tickers", [])),
        ]
        new_rows.append(row)

    new_count = len(new_rows)
    if new_rows:
        _atomic_append_rows(new_rows)
        _remember_ids(newly_seen)

    duration = datetime.now(timezone.utc).timestamp() - start_ts
    _write_metrics({
        "polled_feeds": len(sources),
        "fetched": fetched,
        "new_written": new_count,
        "duration_seconds": round(duration, 3),
        "alpaca_enabled": bool(ALPACA_API_KEY and ALPACA_API_SECRET),
        "custom_scraper": bool(CUSTOM_SCRAPER_FUNCS),
    })

    _log(f"Cycle complete: feeds={len(sources)} fetched={fetched} new={new_count} elapsed={duration:.2f}s")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _log("Interrupted via KeyboardInterrupt.")
        sys.exit(130)
