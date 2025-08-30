# backend/news_ingestor.py
"""
News Ingestor (single-cycle)
- Reads NEWS_SOURCES (comma-separated URLs or JSON array).
- Pulls Alpaca news when configured via "alpaca:SYMB1|SYMB2|...".
- Optionally calls your local news_scraper.py if present, to merge custom items.
- Dedupe + atomic append to backend/news_beliefs.csv.
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

# Optional deps; we degrade gracefully if missing.
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
OUT_CSV = BASE_DIR / "news_beliefs.csv"
METRICS_JSON = BASE_DIR / "news_ingestor_metrics.json"
STATE_JSON = BASE_DIR / "news_ingestor_state.json"  # persistent dedupe/last-run

ALPACA_DATA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log(msg: str):
    print(f"[{_utc_now_iso()}] [news_ingestor] {msg}", flush=True)

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
        return []
    # Allow JSON array or comma-separated
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    return [s.strip() for s in raw.split(",") if s.strip()]

def _csv_header() -> List[str]:
    return ["timestamp_utc", "story_id", "title", "url", "source", "summary", "tickers"]

def _ensure_csv():
    if not OUT_CSV.exists():
        with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(_csv_header())

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
        _log(f"ERROR parsing feed {url}: {e}")
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
        story_id = it.get("id") or it.get("uuid") or it.get("url") or it.get("title")
        out.append({
            "story_id": str(story_id) if story_id else None,
            "title": it.get("title", ""),
            "url": it.get("url", ""),
            "source": url,
            "summary": it.get("summary", "") or it.get("description", ""),
            "tickers": it.get("tickers", []) or it.get("symbols", []),
        })
    return out

def _fetch_alpaca_news(symbols: List[str], limit: int = 50, timeout: int = 10) -> List[Dict]:
    """
    Uses Alpaca Market Data v1beta1 news endpoint when keys are present.
    NOTE: This assumes Premium data access is enabled in your Alpaca account.
    """
    if requests is None:
        _log("WARNING: requests not installed; skipping Alpaca news.")
        return []
    if not (ALPACA_API_KEY and ALPACA_API_SECRET):
        _log("INFO: Alpaca keys not set; skipping Alpaca news.")
        return []
    if not symbols:
        return []

    url = f"{ALPACA_DATA_BASE.rstrip('/')}/v1beta1/news"
    params = {"symbols": ",".join(symbols), "limit": str(limit)}
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
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
        return ("auto", {"url": entry})
    return ("unknown", {"raw": entry})

def _collect_entries(sources: List[str]) -> List[Dict]:
    collected: List[Dict] = []

    # 1) Built-in sources
    for s in sources:
        kind, meta = _infer_fetcher(s)
        if kind == "alpaca":
            entries = _fetch_alpaca_news(meta.get("symbols", []))
            _log(f"Source alpaca:{'|'.join(meta.get('symbols', []))} -> {len(entries)} items")
            collected.extend(entries)
        elif kind == "auto":
            url = meta["url"]
            rss_entries = _fetch_rss(url)
            if rss_entries:
                _log(f"Source RSS {url} -> {len(rss_entries)} items")
                collected.extend(rss_entries)
            else:
                json_entries = _fetch_http_json(url)
                _log(f"Source JSON {url} -> {len(json_entries)} items")
                collected.extend(json_entries)
        elif kind == "rss":
            url = meta["url"]
            rss_entries = _fetch_rss(url)
            _log(f"Source RSS {url} -> {len(rss_entries)} items")
            collected.extend(rss_entries)
        else:
            _log(f"WARNING: Unrecognized source '{s}', skipping.")

    # 2) Optional custom scraper hook (your news_scraper.py)
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
        it["url"] = _normalize_text(it.get("url"))
        it["source"] = _normalize_text(it.get("source"))
        it["summary"] = _normalize_text(it.get("summary"))
        syms = it.get("tickers") or []
        if not isinstance(syms, list):
            syms = [str(syms)]
        it["tickers"] = sorted({str(t).upper() for t in syms if str(t).strip()})
    return collected

def _write_metrics(metrics: Dict):
    metrics = dict(metrics)
    metrics["last_run_utc"] = _utc_now_iso()
    _atomic_write_text(METRICS_JSON, json.dumps(metrics, indent=2))

def main():
    # Support one-shot invocation, loop is external
    _ = sys.argv[1:]

    sources = _parse_sources_env()
    if not sources and not CUSTOM_SCRAPER_FUNCS:
        _log("INFO: NEWS_SOURCES is empty and no custom scraper detected; nothing to ingest.")
        _write_metrics({
            "polled_feeds": 0, "fetched": 0, "new_written": 0, "duration_seconds": 0.0,
            "alpaca_enabled": bool(ALPACA_API_KEY and ALPACA_API_SECRET),
            "custom_scraper": False,
        })
        return 0

    start_ts = datetime.now(timezone.utc).timestamp()

    entries = _collect_entries(sources)
    fetched = len(entries)
    seen = _load_seen_ids()

    # dedupe by story_id (fallback to URL if missing)
    new_rows: List[List[str]] = []
    newly_seen: List[str] = []

    for it in entries:
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
