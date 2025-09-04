# ============================================================
# backend/signal_mapping/creative_mapper.py
# ============================================================
# PURPOSE:
#   - "Creative Mapping" engine for vague/cultural beliefs.
#   - Converts natural-language beliefs (e.g. "Taylor Swift is
#     moving markets") into plausible tickers.
#
# DESIGN:
#   - Lightweight heuristics (entity extraction + news co-mentions).
#   - Uses backend/data_sources/alpaca_news.py for news fetching.
#   - Live-loaded cultural triggers from JSON config (hot-reloadable).
#   - Strict ticker validation (avoids false positives).
#   - Ranked candidates with scores + explanations.
#
# SAFETY:
#   - No side effects, no network calls except via alpaca_news.
#   - If Alpaca API is not available, returns [].
#   - Cultural triggers as fallback only when news is empty.
#   - If nothing clears threshold → fallback to SPY/QQQ unchanged.
#
# ENV VARS:
#   - CREATIVE_MIN_SCORE (float, default 0.55)
#   - CULTURAL_TRIGGERS_PATH (path to JSON, default: backend/config/cultural_triggers.json)
#
# USAGE:
#   from backend.signal_mapping.creative_mapper import (
#       generate_symbol_candidates, choose_best_candidate
#   )
#
#   cands = generate_symbol_candidates("Taylor Swift tour drives economy")
#   best = choose_best_candidate(cands)
#   print(best)
# ============================================================

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from collections import Counter
import os
import re
import json
import datetime as dt
from pathlib import Path
import time

from backend.data_sources.alpaca_news import search_news, get_trending_symbols

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
STOPWORD_TICKERS = {"S", "ON", "ALL", "FOR", "IT", "A", "AN", "THE", "NEXT", "IN", "IS"}
MIN_TICKER_LEN   = 2  # avoid single-letter noise like "I"
MIN_ACCEPT_SCORE = float(os.getenv("CREATIVE_MIN_SCORE", "0.55"))

# ------------------------------------------------------------
# LIVE CULTURAL TRIGGERS SYSTEM
# ------------------------------------------------------------
class CulturalTriggerManager:
    """Manages live-loaded cultural triggers with caching and hot-reload."""
    def __init__(self):
        default_path = Path(__file__).parent.parent / "config" / "cultural_triggers.json"
        self.triggers_path = Path(os.getenv("CULTURAL_TRIGGERS_PATH", str(default_path)))
        self._cache = {}
        self._last_loaded = 0.0
        self._cache_ttl = 60  # seconds

        # Minimal fallback triggers if JSON fails
        self._fallback_triggers = {
            "taylor swift": {
                "tickers": ["LYV", "SPOT", "WMG", "PINS"],
                "confidence": 0.65,
                "category": "celebrity"
            },
            "super bowl": {
                "tickers": ["DIS", "DKNG", "NKE", "CMCSA"],
                "confidence": 0.62,
                "category": "sports"
            },
            "black friday": {
                "tickers": ["AMZN", "WMT", "TGT", "SHOP"],
                "confidence": 0.60,
                "category": "shopping"
            },
            "ai boom": {
                "tickers": ["NVDA", "MSFT", "GOOGL", "PLTR"],
                "confidence": 0.68,
                "category": "tech"
            },
            "recession": {
                "tickers": ["GLD", "TLT", "SH", "UUP"],
                "confidence": 0.58,
                "category": "macro"
            }
        }

    def _load_from_file(self) -> Dict:
        """Load triggers from JSON file; fall back to baked-in set on error."""
        try:
            if self.triggers_path.exists():
                with open(self.triggers_path, "r") as f:
                    data = json.load(f)
                triggers = data.get("triggers", {})
                if "version" in data:
                    print(f"[CULTURAL_TRIGGERS] Loaded v{data['version']} from {self.triggers_path}")
                return triggers
        except Exception as e:
            print(f"[CULTURAL_TRIGGERS] Error loading JSON: {e}")
        return self._fallback_triggers

    def get_triggers(self) -> Dict:
        """Get triggers with hot-reload capability (mtime + ttl)."""
        now = time.time()
        should_reload = False
        if now - self._last_loaded > self._cache_ttl:
            should_reload = True
        elif self.triggers_path.exists():
            try:
                file_mtime = self.triggers_path.stat().st_mtime
                if file_mtime > self._last_loaded:
                    should_reload = True
            except Exception:
                should_reload = True

        if should_reload or not self._cache:
            self._cache = self._load_from_file()
            self._last_loaded = now
        return self._cache

    def record_usage(self, trigger: str, ticker: str, success: Optional[bool] = None):
        """Record trigger usage for future learning (stdout stub; optional file later)."""
        timestamp = dt.datetime.utcnow().isoformat()
        print(f"[TRIGGER_USAGE] {timestamp} | trigger={trigger} | ticker={ticker} | success={success}")
        # Future: write to JSONL in self.triggers_path.parent if desired.

# Initialize the trigger manager (module-level singleton)
trigger_manager = CulturalTriggerManager()

# ------------------------------------------------------------
# VALIDATION HELPERS
# ------------------------------------------------------------
def _is_valid_equity_symbol(sym: str) -> bool:
    """Strict filter to ensure only valid equity tickers pass through."""
    if not sym:
        return False
    s = sym.upper()
    if s in STOPWORD_TICKERS:
        return False
    if len(s) < MIN_TICKER_LEN:
        return False
    if len(s) > 5 and "." not in s:  # allow BRK.B style
        return False
    if not all(c.isalnum() or c == "." for c in s):
        return False
    blacklist = {"USD", "EUR", "GBP", "JPY", "BTC", "ETH", "VIX", "DXY"}
    return s not in blacklist

def _time_decay(created_at_iso: str, half_life_days: float = 7.0) -> float:
    """Exponential decay weighting: recent news counts more."""
    try:
        t = dt.datetime.fromisoformat(created_at_iso.replace("Z", "+00:00")).replace(tzinfo=None)
        delta_days = max(0.0, (dt.datetime.utcnow() - t).days)
        return 0.5 ** (delta_days / half_life_days)
    except Exception:
        return 1.0

# ------------------------------------------------------------
# ENTITY EXTRACTION
# ------------------------------------------------------------
def extract_entities(belief: str) -> List[str]:
    """
    Minimal NLP to extract candidate entities:
      - Proper nouns (capitalized words or bigrams).
      - Keywords > 3 chars not in stop words.
    """
    if not belief:
        return []
    stop_words = {
        "the","will","going","think","believe","market","stock","stocks","equities",
        "price","up","down","buy","sell","long","short","is","are","a","an","to","of","and","in"
    }
    raw = [t.strip(",.!?:;") for t in belief.split()]
    proper = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", belief)
    keywords = [w for w in (t.lower() for t in raw) if len(w) > 3 and w not in stop_words]
    seen, out = set(), []
    for tok in proper + keywords:
        k = tok.lower()
        if k not in seen:
            seen.add(k); out.append(tok)
    return out[:5]  # cap noise

# ------------------------------------------------------------
# CULTURAL TRIGGER DETECTION
# ------------------------------------------------------------
def _detect_cultural_triggers(belief: str) -> List[Tuple[str, Dict]]:
    """
    Check if belief contains any cultural triggers.
    Returns list of (trigger_phrase, trigger_data) tuples.
    """
    if not belief:
        return []
    belief_lower = belief.lower()
    matches: List[Tuple[str, Dict]] = []
    triggers = trigger_manager.get_triggers()
    for phrase, data in triggers.items():
        if phrase in belief_lower:
            if isinstance(data, dict):
                tickers = data.get("tickers", [])
                confidence = float(data.get("confidence", 0.60))
                category = data.get("category", "general")
            else:
                tickers = data if isinstance(data, list) else []
                confidence = 0.60
                category = "general"
            valid = [t for t in tickers if _is_valid_equity_symbol(t)]
            if valid:
                matches.append((phrase, {"tickers": valid, "confidence": confidence, "category": category}))
    return matches

# ------------------------------------------------------------
# SCORING
# ------------------------------------------------------------
def _score_symbol_from_news(symbol: str, news_items: List[Dict], entities: List[str]) -> float:
    """
    Score = frequency (time-decayed) + entity overlaps in headlines/summary.
    Returns float between 0.0–1.0.
    """
    if not news_items:
        return 0.0
    freq = 0.0
    entity_hits = 0.0
    for item in news_items:
        if symbol in [s.upper() for s in (item.get("symbols") or [])]:
            freq += _time_decay(item.get("created_at", ""))
        head = (item.get("headline") or "").lower()
        summ = (item.get("summary") or "").lower()
        for e in entities:
            el = e.lower()
            if el and (el in head or el in summ):
                entity_hits += 0.2
    return min(1.0, freq * 0.6 + entity_hits)

# ------------------------------------------------------------
# TRENDING FALLBACK (last resort)
# ------------------------------------------------------------
def _try_trending_fallback(belief_text: str) -> List[Dict]:
    """
    Try to get trending symbols as last resort.
    Only for beliefs that seem time-sensitive.
    """
    time_words = {"today", "now", "tonight", "this week", "breaking", "trending", "hot", "current", "latest"}
    bl = (belief_text or "").lower()
    if any(w in bl for w in time_words):
        try:
            trending = get_trending_symbols(limit=5)
            if trending:
                return [
                    {
                        "symbol": sym,
                        "score": max(0.56, MIN_ACCEPT_SCORE + 0.01),  # allow pass if it's our *only* signal
                        "why": "Currently trending symbol (time-sensitive fallback)"
                    }
                    for sym in trending if _is_valid_equity_symbol(sym)
                ]
        except Exception:
            pass
    return []

# ------------------------------------------------------------
# MAIN: generate_symbol_candidates
# ------------------------------------------------------------
def generate_symbol_candidates(belief: str, since_days: int = 14) -> List[Dict]:
    """
    Generate candidate tickers for a belief:
      1) Extract entities from the belief.
      2) Search Alpaca News for those entities.
      3) If news returns candidates → score and return them.
      4) If news is empty → cultural triggers fallback.
      5) If still empty → trending fallback for time-sensitive beliefs.
    """
    entities = extract_entities(belief)
    all_news: List[Dict] = []

    # 1) News query by entities
    q = " ".join(entities[:3]) if entities else ""
    if q:
        all_news.extend(search_news(query=q, since_days=since_days, limit=50))

    # 2) If news returned items → score ranking
    if all_news:
        symbol_articles: Dict[str, List[Dict]] = {}
        for item in all_news:
            for s in item.get("symbols") or []:
                su = str(s).upper()
                if _is_valid_equity_symbol(su):
                    symbol_articles.setdefault(su, []).append(item)

        if symbol_articles:
            scored = [(sym, _score_symbol_from_news(sym, items, entities)) for sym, items in symbol_articles.items()]
            scored.sort(key=lambda x: x[1], reverse=True)

            out: List[Dict] = []
            for sym, score in scored[:8]:
                arts = symbol_articles.get(sym, [])[:3]
                why_bits = [f"{a.get('source','news')}: {a.get('headline','')}" for a in arts]
                why = " | ".join(why_bits) if why_bits else "Co-mentioned in recent news."
                out.append({"symbol": sym, "score": round(float(score), 3), "why": why})
            return out

    # 3) Cultural triggers if news empty
    cultural_matches = _detect_cultural_triggers(belief)
    if cultural_matches:
        out: List[Dict] = []
        seen = set()
        for phrase, data in cultural_matches:
            base_conf = float(data["confidence"])
            category = data["category"]
            for idx, tkr in enumerate(data["tickers"][:4]):  # top 4 per trigger
                if tkr not in seen:
                    seen.add(tkr)
                    score = base_conf - (idx * 0.03)  # small decay
                    why = f"Cultural trigger [{category}]: '{phrase}' → {tkr}"
                    out.append({"symbol": tkr, "score": round(score, 3), "why": why})
                    trigger_manager.record_usage(phrase, tkr)
        out.sort(key=lambda x: x["score"], reverse=True)
        if out:
            return out[:8]

    # 4) Trending as last resort for time-sensitive beliefs
    trending_candidates = _try_trending_fallback(belief)
    if trending_candidates:
        return trending_candidates[:8]

    # 5) No candidates anywhere
    return []

# ------------------------------------------------------------
# MAIN: choose_best_candidate
# ------------------------------------------------------------
def choose_best_candidate(candidates: List[Dict]) -> Dict:
    """
    Pick the best candidate that clears score threshold.
    Returns {} if no good candidate.
    """
    if not candidates:
        return {}
    best = max(candidates, key=lambda c: c.get("score", 0.0))
    return best if best.get("score", 0.0) >= MIN_ACCEPT_SCORE else {}

# ------------------------------------------------------------
# ADMIN/LEARNING FUNCTIONS (optional)
# ------------------------------------------------------------
def add_cultural_trigger(phrase: str, tickers: List[str], confidence: float = 0.60, category: str = "general") -> bool:
    """
    Add a new cultural trigger programmatically (optional utility).
    """
    try:
        triggers = trigger_manager.get_triggers()
        triggers[phrase.lower()] = {
            "tickers": tickers,
            "confidence": confidence,
            "category": category,
            "added_at": dt.datetime.utcnow().isoformat(),
            "added_by": "system"
        }
        data = {
            "version": "1.1.0",
            "last_updated": dt.datetime.utcnow().isoformat(),
            "triggers": triggers
        }
        # Ensure directory exists (safe write)
        trigger_manager.triggers_path.parent.mkdir(parents=True, exist_ok=True)
        with open(trigger_manager.triggers_path, "w") as f:
            json.dump(data, f, indent=2)
        trigger_manager._cache = {}  # force reload
        return True
    except Exception as e:
        print(f"[ADD_TRIGGER ERROR] {e}")
        return False

def get_trigger_stats() -> Dict:
    """Return simple stats about cultural triggers."""
    triggers = trigger_manager.get_triggers()
    categories: Dict[str, int] = {}
    for phrase, data in triggers.items():
        if isinstance(data, dict):
            cat = data.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1
    return {
        "total_triggers": len(triggers),
        "categories": categories,
        "last_reload": dt.datetime.fromtimestamp(trigger_manager._last_loaded).isoformat(),
        "config_path": str(trigger_manager.triggers_path)
    }
