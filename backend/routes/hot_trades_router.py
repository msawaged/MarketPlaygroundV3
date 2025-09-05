# backend/routes/hot_trades_router.py
"""
Hot Trades Router - Surfaces news-driven trading strategies
Fetches beliefs from news ingestor, enriches with strategies, returns normalized JSON
"""

import os
import csv
import json
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, Query, HTTPException
from backend.ai_engine.ai_engine import run_ai_engine
from backend.utils.logger import write_training_log

# Initialize router
router = APIRouter()

# File paths
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_BELIEFS_CSV = os.path.join(BACKEND_DIR, "news_beliefs.csv")
STRATEGY_OUTCOMES_CSV = os.path.join(BACKEND_DIR, "strategy_outcomes.csv")

def safe_read_csv(filepath: str) -> List[Dict[str, Any]]:
    """Read CSV safely with error handling"""
    if not os.path.exists(filepath):
        print(f"[hot_trades] File not found: {filepath}")
        return []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"[hot_trades] Error reading {filepath}: {e}")
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

def generate_hot_trade_item(
    belief_data: Dict[str, Any],
    strategy_data: Optional[Dict[str, Any]] = None,
    item_id: int = 0
) -> Dict[str, Any]:
    """Generate a normalized hot trade item"""
    
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
    
    # Generate strategy if missing
    if not hot_trade['strategy'] and belief_text:
        try:
            print(f"[hot_trades] Generating strategy for: {belief_text[:50]}...")
            
            ai_result = run_ai_engine(
                belief=belief_text,
                risk_profile="moderate",
                user_id="hot_trades"
            )
            
            if ai_result and 'strategy' in ai_result:
                strategy_obj = ai_result.get('strategy', {})
                
                hot_trade['strategy'] = {
                    'type': strategy_obj.get('type', 'Options Strategy'),
                    'expiration': strategy_obj.get('expiration'),
                    'target_return': strategy_obj.get('target_return'),
                    'max_loss': strategy_obj.get('max_loss'),
                    'max_profit': strategy_obj.get('max_profit')
                }
                
                hot_trade['sentiment'] = normalize_sentiment(ai_result.get('direction', 'neutral'))
                hot_trade['confidence'] = normalize_confidence(ai_result.get('confidence', 0.5))
        except Exception as e:
            print(f"[hot_trades] Error generating strategy: {e}")
            hot_trade['strategy'] = {'type': 'Error', 'error': True}
    
    # Final normalization
    hot_trade['sentiment'] = normalize_sentiment(hot_trade['sentiment'])
    hot_trade['confidence'] = normalize_confidence(hot_trade['confidence'])
    
    if hot_trade['strategy'] is None:
        hot_trade['strategy'] = {'type': 'No strategy', 'error': True}
    
    return hot_trade

@router.get("/hot_trades")
async def get_hot_trades(
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="created_at", regex="^(confidence|created_at)$")
) -> List[Dict[str, Any]]:
    """GET /hot_trades endpoint"""
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
            
            # Generate item
            hot_trade = generate_hot_trade_item(belief, strategy_data, idx)
            hot_trades.append(hot_trade)
            
            if len(hot_trades) >= limit * 2:
                break
        
        # Sort
        if sort == "confidence":
            hot_trades.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        else:
            hot_trades.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        
        # Return limited results
        return hot_trades[:limit]
        
    except Exception as e:
        print(f"[hot_trades] Error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail={"error": str(e)})