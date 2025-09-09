# backend/routes/hot_trades_router.py
"""
Hot Trades Router - Surfaces news-driven trading strategies
Fetches beliefs from news ingestor, enriches with strategies, returns normalized JSON
HARDENED: 30s cache, HOT_TRADES_ENABLED flag, graceful error handling
"""

import os
import csv
import json
import traceback
import time
from datetime import datetime
from typing import List, Dict, Optional, Any, Union
from fastapi import APIRouter, Query, HTTPException
from backend.ai_engine.ai_engine import run_ai_engine
from pathlib import Path

# Initialize router
router = APIRouter()

# === File paths (moved to data/ directory) ===
BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NEWS_BELIEFS_CSV = DATA_DIR / "news_beliefs.csv"
STRATEGY_OUTCOMES_CSV = DATA_DIR / "strategy_outcomes.csv"

# === In-memory cache (30 seconds) ===
CACHE = {
    "data": None,
    "timestamp": 0,
    "ttl": 30  # seconds
}

# === Feature flag ===
HOT_TRADES_ENABLED = os.getenv("HOT_TRADES_ENABLED", "true").lower() == "true"


def safe_read_csv(filepath: Union[str, Path]) -> List[Dict[str, Any]]:
    """Read CSV safely with error handling (Path-safe for Render/CWD differences)."""
    path = Path(filepath)
    if not path.exists():
        print(f"[hot_trades] File not found: {path}")
        return []

    try:
        with path.open('r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"[hot_trades] Error reading {path}: {e}")
        return []


def read_news_beliefs() -> List[Dict[str, Any]]:
    """Read news beliefs from CSV"""
    raw_beliefs = safe_read_csv(NEWS_BELIEFS_CSV)
    beliefs = []
    
    for row in raw_beliefs:
        try:
            # Parse tickers
            tickers_raw = row.get('tickers', '')
            if ';' in tickers_raw:
                tickers = [t.strip() for t in tickers_raw.split(';') if t.strip()]
            else:
                tickers = [tickers_raw.strip()] if tickers_raw.strip() else []
            
            beliefs.append({
                'timestamp': row.get('timestamp_utc', row.get('created_at', '')),
                'story_id': row.get('story_id', ''),
                'title': row.get('title', row.get('headline', '')),
                'url': row.get('url', ''),
                'source': row.get('source', ''),
                'summary': row.get('summary', ''),
                'tickers': tickers,
                'belief': row.get('belief', '')
            })
        except Exception as e:
            print(f"[hot_trades] Error parsing belief row: {e}")
            continue
    
    return beliefs


def read_strategy_outcomes() -> Dict[str, Dict[str, Any]]:
    """Read strategy outcomes from CSV"""
    raw_strategies = safe_read_csv(STRATEGY_OUTCOMES_CSV)
    strategies = {}
    
    for row in raw_strategies:
        try:
            belief_key = row.get('belief', '').strip()
            if not belief_key:
                continue
            
            pnl_str = row.get('pnl_percent', '0')
            try:
                pnl = float(str(pnl_str).replace('%', ''))
            except:
                pnl = 0.0
            
            strategies[belief_key] = {
                'strategy': row.get('strategy', ''),
                'ticker': row.get('ticker', ''),
                'pnl_percent': pnl,
                'result': row.get('result', ''),
                'risk': row.get('risk', 'moderate'),
                'notes': row.get('notes', '')
            }
        except Exception as e:
            print(f"[hot_trades] Error parsing strategy row: {e}")
            continue
    
    return strategies


def normalize_sentiment(value: Any) -> str:
    """Convert to bullish/bearish/neutral"""
    if value is None or value == '':
        return "neutral"
    
    if isinstance(value, str):
        value_lower = value.lower()
        if any(word in value_lower for word in ["bull", "positive", "up", "long", "buy"]):
            return "bullish"
        elif any(word in value_lower for word in ["bear", "negative", "down", "short", "sell"]):
            return "bearish"
    
    try:
        num = float(value)
        if num > 0.2:
            return "bullish"
        elif num < -0.2:
            return "bearish"
    except:
        pass
    
    return "neutral"


def normalize_confidence(value: Any) -> float:
    """Convert to 0-100 scale"""
    if value is None or value == '':
        return 50.0
    
    try:
        if isinstance(value, str) and '%' in value:
            conf = float(value.replace('%', ''))
        else:
            conf = float(value)
        
        if 0 <= conf <= 1:
            return conf * 100
        elif 0 <= conf <= 100:
            return conf
        else:
            return max(0, min(100, abs(conf)))
    except:
        return 50.0


def normalize_option_legs(strategy_obj: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Normalize option legs to use the final ticker (Fix C from ai_engine.py).
    Only normalize legs if they exist and are options.
    """
    if not strategy_obj or not isinstance(strategy_obj, dict):
        return strategy_obj
    
    legs = strategy_obj.get('legs', [])
    if not legs:
        return strategy_obj
    
    normalized_legs = []
    for leg in legs:
        if not isinstance(leg, dict):
            normalized_legs.append(leg)
            continue
            
        # Only normalize if it's an option leg
        option_type = leg.get('option_type')
        if option_type in ['call', 'put']:
            # Force ticker to the final ticker
            leg['ticker'] = ticker
        
        normalized_legs.append(leg)
    
    strategy_obj['legs'] = normalized_legs
    return strategy_obj


def generate_hot_trade_item(
    belief_data: Dict[str, Any],
    strategy_data: Optional[Dict[str, Any]] = None,
    item_id: int = 0
) -> Dict[str, Any]:
    """Generate a normalized hot trade item with error handling"""
    
    # Get belief text
    belief_text = (
        belief_data.get('belief', '') or 
        belief_data.get('title', '') or 
        belief_data.get('summary', '')
    ).strip()
    
    # Get ticker
    tickers = belief_data.get('tickers', [])
    ticker = tickers[0] if tickers else 'SPY'
    
    # Build hot trade item
    hot_trade = {
        'id': item_id,
        'ticker': ticker.upper(),
        'headline': belief_data.get('title', 'Market Update'),
        'source': belief_data.get('source', 'alpaca'),
        'belief': belief_text or 'No belief text',
        'sentiment': 'neutral',
        'confidence': 50.0,
        'strategy': None,
        'createdAt': belief_data.get('timestamp', datetime.utcnow().isoformat())
    }
    
    # Use existing strategy if available
    if strategy_data:
        hot_trade['strategy'] = {
            'type': strategy_data.get('strategy', 'Unknown'),
            'risk_level': strategy_data.get('risk', 'moderate')
        }
        
        if strategy_data.get('result') == 'win':
            hot_trade['sentiment'] = 'bullish'
        elif strategy_data.get('result') == 'loss':
            hot_trade['sentiment'] = 'bearish'
        
        try:
            pnl = float(strategy_data.get('pnl_percent', 0))
            hot_trade['confidence'] = min(100, max(0, 50 + pnl))
        except:
            pass
    
    # Generate strategy if missing (with error handling)
    if not hot_trade['strategy'] and belief_text:
        try:
            print(f"[hot_trades] Generating strategy for: {belief_text[:50]}...")
            
            ai_result = run_ai_engine(
                belief=belief_text,
                risk_profile="moderate",
                user_id="hot_trades"
            )
            
            if ai_result and isinstance(ai_result, dict) and 'strategy' in ai_result:
                strategy_obj = ai_result.get('strategy', {})
                
                # Normalize option legs to use final ticker
                strategy_obj = normalize_option_legs(strategy_obj, ticker)
                
                hot_trade['strategy'] = {
                    'type': strategy_obj.get('type', 'Options Strategy'),
                    'expiration': strategy_obj.get('expiration'),
                    'target_return': strategy_obj.get('target_return'),
                    'max_loss': strategy_obj.get('max_loss'),
                    'max_profit': strategy_obj.get('max_profit')
                }
                
                hot_trade['sentiment'] = normalize_sentiment(ai_result.get('direction', 'neutral'))
                hot_trade['confidence'] = normalize_confidence(ai_result.get('confidence', 0.5))
            else:
                # GPT returned invalid response
                print(f"[hot_trades] GPT returned invalid response for: {belief_text[:30]}")
                hot_trade['strategy'] = {'type': 'Unavailable (invalid response)', 'error': True}
                
        except Exception as e:
            print(f"[hot_trades] Error generating strategy: {e}")
            # Check if it's a quota error
            if "quota" in str(e).lower() or "rate" in str(e).lower():
                hot_trade['strategy'] = {'type': 'Unavailable (quota)', 'error': True}
            else:
                hot_trade['strategy'] = {'type': 'Unavailable (error)', 'error': True}
    
    # Final normalization
    hot_trade['sentiment'] = normalize_sentiment(hot_trade['sentiment'])
    hot_trade['confidence'] = normalize_confidence(hot_trade['confidence'])
    
    if hot_trade['strategy'] is None:
        hot_trade['strategy'] = {'type': 'No strategy', 'error': True}
    
    return hot_trade


def generate_placeholder_trades() -> List[Dict[str, Any]]:
    """Generate placeholder trades when feature is disabled or on error"""
    return [{
        'id': 0,
        'ticker': 'SPY',
        'headline': 'Hot trades temporarily unavailable',
        'source': 'system',
        'belief': 'Hot trades feature is currently disabled or experiencing issues',
        'sentiment': 'neutral',
        'confidence': 0.0,
        'strategy': {'type': 'Unavailable', 'error': True},
        'createdAt': datetime.utcnow().isoformat()
    }]


@router.get("/hot_trades")
async def get_hot_trades(
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="created_at", regex="^(confidence|created_at)$")
) -> List[Dict[str, Any]]:
    """GET /hot_trades endpoint with caching and error handling"""
    
    # Check feature flag
    if not HOT_TRADES_ENABLED:
        print("[hot_trades] Feature disabled via HOT_TRADES_ENABLED env var")
        return []
    
    # Check cache
    current_time = time.time()
    if CACHE["data"] is not None and (current_time - CACHE["timestamp"]) < CACHE["ttl"]:
        print(f"[hot_trades] Returning cached data (age: {current_time - CACHE['timestamp']:.1f}s)")
        cached_data = CACHE["data"]
        
        # Apply sorting and limiting to cached data
        if sort == "confidence":
            cached_data = sorted(cached_data, key=lambda x: x.get('confidence', 0), reverse=True)
        else:
            cached_data = sorted(cached_data, key=lambda x: x.get('createdAt', ''), reverse=True)
        
        return cached_data[:limit]
    
    try:
        # Load data
        beliefs = read_news_beliefs()
        strategies = read_strategy_outcomes()
        
        print(f"[hot_trades] Processing {len(beliefs)} beliefs, {len(strategies)} strategies")
        
        # Generate hot trade items
        hot_trades = []
        
        for idx, belief in enumerate(beliefs[:limit * 2]):
            # Match strategy
            belief_key = belief.get('title', '')
            strategy_data = strategies.get(belief_key)
            
            if not strategy_data and belief.get('summary'):
                strategy_data = strategies.get(belief.get('summary', ''))
            
            # Generate item (with error handling built in)
            hot_trade = generate_hot_trade_item(belief, strategy_data, idx)
            hot_trades.append(hot_trade)
            
            if len(hot_trades) >= limit * 2:
                break
        
        # If no trades generated, return placeholder
        if not hot_trades:
            hot_trades = generate_placeholder_trades()
        
        # Update cache
        CACHE["data"] = hot_trades
        CACHE["timestamp"] = current_time
        print(f"[hot_trades] Cache updated with {len(hot_trades)} items")
        
        # Sort
        if sort == "confidence":
            hot_trades.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        else:
            hot_trades.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        
        # Return limited results
        return hot_trades[:limit]
        
    except Exception as e:
        print(f"[hot_trades] Critical error: {e}")
        traceback.print_exc()
        
        # Return graceful fallback instead of raising exception
        return generate_placeholder_trades()