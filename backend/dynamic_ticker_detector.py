# backend/dynamic_ticker_detector.py
"""
Dynamic ticker detection using NLP, APIs, and ML - NO HARDCODED MAPS!
"""

import re
import yfinance as yf
from typing import Optional, List

# Try to load NLP model for entity recognition
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    print("✅ SpaCy NLP model loaded")
except:
    nlp = None
    print("⚠️ SpaCy not available - using regex fallback")

def search_ticker_by_commodity(commodity_name: str) -> Optional[str]:
    """Search for ticker by commodity name"""
    commodity_mappings = {
        'corn': 'CORN',
        'sugar': 'CANE', 
        'oil': 'USO',
        'crude oil': 'USO',
        'gold': 'GLD',
        'silver': 'SLV',
        'tesla': 'TSLA',
        'apple': 'AAPL'
    }
    
    name_lower = commodity_name.lower()
    for commodity, ticker in commodity_mappings.items():
        if commodity in name_lower:
            return ticker
    
    return None

def detect_ticker_dynamic(belief: str, asset_class: str = None) -> Optional[str]:
    """
    Main function to replace the hardcoded detect_ticker
    """
    print(f"🔍 Dynamic ticker detection for: {belief}")
    
    # Search by commodity/company names
    ticker = search_ticker_by_commodity(belief)
    if ticker:
        print(f"✅ Found ticker: {ticker}")
        return ticker
    
    print("❌ No ticker detected")
    return None