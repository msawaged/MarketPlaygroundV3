# FILE: backend/ai_engine/gpt4_strategy_generator.py
"""
GPT-4 Strategy Generator — Isolated GPT wrapper that turns beliefs into trading strategies.
ENHANCED VERSION: Professional-grade prompts with MARKET PRICE CONTEXT
"""

import os
import json
from typing import Optional
import yfinance as yf
import re

from backend.openai_config import OPENAI_API_KEY, GPT_MODEL
import openai

# ⛔️ DO NOT initialize client immediately due to compatibility issues with 'proxies'
# ✅ Use lazy loading — only create the client once, when needed
client = None

def initialize_openai_client():
    """
    Lazy-initialize the OpenAI client once, if needed.
    Prevents import-time failures and allows for better error handling.
    """
    global client
    if client is None:
        try:
            print("🔑 Initializing OpenAI client...")
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            print("✅ OpenAI client initialized successfully.")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI client: {e}")
            client = None
    return client


def extract_ticker_from_belief(belief: str) -> Optional[str]:
    """
    Extract ticker symbol from user belief using multiple methods.
    
    Args:
        belief (str): User's market belief
        
    Returns:
        Optional[str]: Ticker symbol if found, None otherwise
    """
    # Common ticker patterns
    ticker_patterns = [
        r'\b([A-Z]{1,5})\b',  # 1-5 uppercase letters
        r'\$([A-Z]{1,5})\b',  # $TICKER format
    ]
    
    # Company name to ticker mapping (expand as needed)
    company_mappings = {
        'tesla': 'TSLA',
        'apple': 'AAPL', 
        'microsoft': 'MSFT',
        'amazon': 'AMZN',
        'google': 'GOOGL',
        'nvidia': 'NVDA',
        'meta': 'META',
        'netflix': 'NFLX',
        'spotify': 'SPOT',
        'uber': 'UBER',
        'bitcoin': 'BTC-USD',
        'ethereum': 'ETH-USD'
    }
    
    belief_lower = belief.lower()
    
    # Check company name mappings first
    for company, ticker in company_mappings.items():
        if company in belief_lower:
            return ticker
    
    # Then check ticker patterns
    for pattern in ticker_patterns:
        matches = re.findall(pattern, belief.upper())
        if matches:
            # Return first valid ticker (could add validation here)
            return matches[0]
    
    return None


def get_current_price(ticker: str) -> Optional[float]:
    """
    Fetch current market price for given ticker.
    
    Args:
        ticker (str): Stock ticker symbol
        
    Returns:
        Optional[float]: Current price or None if failed
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Try multiple price fields
        price_fields = ['currentPrice', 'regularMarketPrice', 'previousClose']
        
        for field in price_fields:
            if field in info and info[field]:
                price = float(info[field])
                print(f"📊 {ticker} current price: ${price:.2f}")
                return price
                
        print(f"⚠️ Could not fetch price for {ticker}")
        return None
        
    except Exception as e:
        print(f"❌ Error fetching price for {ticker}: {e}")
        return None


def get_strike_guidelines(current_price: float, sentiment: str) -> dict:
    """
    Generate strike price guidelines based on current price and sentiment.
    
    Args:
        current_price (float): Current stock price
        sentiment (str): 'bullish', 'bearish', or 'neutral'
        
    Returns:
        dict: Strike price guidelines and reasoning
    """
    if sentiment.lower() in ['bullish', 'bull', 'up', 'rise', 'increase']:
        # For bullish sentiment: ATM to slightly OTM calls
        atm_strike = round(current_price, 0)
        otm_strike = round(current_price * 1.05, 0)  # 5% OTM
        
        return {
            'sentiment': 'bullish',
            'recommended_strikes': f"${atm_strike:.0f} - ${otm_strike:.0f}",
            'strategy_type': 'Call Options',
            'reasoning': f"With {current_price:.2f} current price, ATM-OTM calls provide optimal leverage for upward movement"
        }
        
    elif sentiment.lower() in ['bearish', 'bear', 'down', 'fall', 'decrease']:
        # For bearish sentiment: ATM to slightly OTM puts
        atm_strike = round(current_price, 0)
        otm_strike = round(current_price * 0.95, 0)  # 5% OTM
        
        return {
            'sentiment': 'bearish', 
            'recommended_strikes': f"${otm_strike:.0f} - ${atm_strike:.0f}",
            'strategy_type': 'Put Options',
            'reasoning': f"With {current_price:.2f} current price, ATM-OTM puts provide optimal leverage for downward movement"
        }
        
    else:
        # Neutral/unclear sentiment
        return {
            'sentiment': 'neutral',
            'recommended_strikes': f"${current_price*0.95:.0f} - ${current_price*1.05:.0f}",
            'strategy_type': 'Neutral Strategy',
            'reasoning': f"Current price ${current_price:.2f} - consider range-bound strategies"
        }


def validate_strategy_logic(strategy: dict, current_price: float, belief: str) -> bool:
    """
    Validate that the generated strategy makes logical sense.
    
    Args:
        strategy (dict): Generated strategy
        current_price (float): Current market price
        belief (str): Original user belief
        
    Returns:
        bool: True if strategy is logical, False otherwise
    """
    try:
        trade_legs = strategy.get('trade_legs', [])
        if not trade_legs:
            print("❌ Validation failed: No trade legs found")
            return False
            
        # Check for bullish belief with calls
        belief_lower = belief.lower()
        is_bullish = any(word in belief_lower for word in ['up', 'rise', 'bull', 'increase', 'moon'])
        is_bearish = any(word in belief_lower for word in ['down', 'fall', 'bear', 'decrease', 'crash'])
        
        for leg in trade_legs:
            strike_price = float(leg.get('strike_price', 0))
            option_type = leg.get('option_type', '').lower()
            
            # Validate strike price is reasonable (within 20% of current price)
            price_diff_pct = abs(strike_price - current_price) / current_price
            if price_diff_pct > 0.20:
                print(f"❌ Validation failed: Strike ${strike_price} too far from current ${current_price:.2f}")
                return False
                
            # Validate sentiment alignment
            if is_bullish and option_type == 'put':
                print("❌ Validation failed: Bullish belief with put options")
                return False
                
            if is_bearish and option_type == 'call':
                print("❌ Validation failed: Bearish belief with call options") 
                return False
        
        print("✅ Strategy validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        return False


def generate_strategy_with_gpt4(belief: str) -> Optional[dict]:
    """
    Send the user belief to GPT-4 with ENHANCED institutional-grade prompts.
    NOW INCLUDES: Current market price context and strike price guidelines
    
    Args:
        belief (str): User's market belief/thesis
        
    Returns:
        Optional[dict]: Detailed strategy dict with professional analysis,
                       or None if GPT fails or response is invalid
    """
    openai_client = initialize_openai_client()
    if not openai_client:
        print("⚠️ OpenAI client unavailable. Aborting GPT-4 strategy generation.")
        return None

    # 📊 EXTRACT TICKER AND FETCH CURRENT PRICE
    ticker = extract_ticker_from_belief(belief)
    current_price = None
    strike_guidelines = None
    
    if ticker:
        current_price = get_current_price(ticker)
        if current_price:
            # Determine sentiment and get guidelines
            sentiment = 'bullish' if any(word in belief.lower() for word in ['up', 'rise', 'bull', 'increase']) else 'bearish' if any(word in belief.lower() for word in ['down', 'fall', 'bear', 'decrease']) else 'neutral'
            strike_guidelines = get_strike_guidelines(current_price, sentiment)

    # 🎯 ENHANCED SYSTEM PROMPT: Now includes price awareness
    system_prompt = (
        "You are an elite institutional trading strategist with 20+ years of experience. "
        "You have access to real-time market data and must consider current prices when selecting strikes. "
        "Provide sophisticated, detailed trading strategies with deep market insights that align with current market context. "
        "Your analysis should include technical, fundamental, and risk considerations. "
        "Always format output as valid JSON with comprehensive explanations."
    )

    # 🔥 ENHANCED USER PROMPT: Now includes current price context
    market_context = ""
    if current_price and strike_guidelines:
        market_context = (
            f"\n\n📊 CURRENT MARKET CONTEXT:\n"
            f"Ticker: {ticker}\n"
            f"Current Price: ${current_price:.2f}\n"
            f"Detected Sentiment: {strike_guidelines['sentiment']}\n"
            f"Recommended Strike Range: {strike_guidelines['recommended_strikes']}\n"
            f"Strategy Focus: {strike_guidelines['strategy_type']}\n"
            f"Reasoning: {strike_guidelines['reasoning']}\n\n"
            f"⚠️ CRITICAL: Select strike prices that make sense relative to ${current_price:.2f}. "
            f"For bullish views, use ATM-OTM calls. For bearish views, use ATM-OTM puts.\n"
        )

    user_prompt = (
        f"Belief: {belief}{market_context}\n"
        "Provide a detailed trading strategy in this JSON format:\n"
        "{\n"
        '  "type": "Call Option",\n'
        '  "trade_legs": [\n'
        '    {"action": "Buy to Open", "ticker": "AAPL", "option_type": "Call", "strike_price": "150"}\n'
        "  ],\n"
        '  "expiration": "2025-09-20",\n'
        '  "target_return": "20%",\n'
        '  "max_loss": "Premium Paid",\n'
        '  "time_to_target": "2 weeks",\n'
        '  "explanation": "Given the current market environment and technical indicators, this call option strategy capitalizes on anticipated earnings momentum in AAPL. The strike price at $150 provides optimal risk-reward positioning above current resistance levels. Key catalysts include strong iPhone sales guidance and AI integration announcements. Risk management involves limiting loss to premium ($2.50/share) while targeting 20% returns within the 2-week window. This strategy benefits from positive gamma and delta exposure while maintaining defined risk parameters. Exit criteria: 50% profit target or 2 days before expiration to avoid theta decay."\n'
        "}\n\n"
        "Requirements:\n"
        "- Use the current price context provided above when selecting strikes\n"
        "- Explanation must be 100+ words with specific market reasoning\n"
        "- Include technical analysis, catalysts, and risk management\n"
        "- Mention specific price targets and exit criteria\n"
        "- Strike prices must be logical relative to current market price\n"
        "- Only output valid JSON, no markdown or extra text"
    )

    try:
        print("🚀 Sending belief to GPT-4 with market context...")
        
        response = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=800,
        )

        gpt_output = response.choices[0].message.content.strip()
        print(f"🔥 GPT raw output:\n{gpt_output}\n")

        # 🔍 JSON PARSING: Attempt to parse GPT response as valid JSON
        strategy = json.loads(gpt_output)
        
        # 🛡️ VALIDATION: Check if strategy makes logical sense
        if current_price and not validate_strategy_logic(strategy, current_price, belief):
            print("❌ Strategy failed validation - regenerating...")
            return None
            
        print("✅ Successfully parsed and validated GPT-4 strategy.")
        return strategy

    except json.JSONDecodeError as je:
        print(f"❌ Failed to parse GPT-4 output as JSON: {je}")
        print("🔍 GPT raw response for manual review:\n", gpt_output)
        return None

    except Exception as e:
        print(f"❌ GPT-4 strategy generation failed: {e}")
        return None

def validate_strategy_sentiment_alignment(strategy_data: dict, user_belief: str, detected_sentiment: str) -> bool:
    """
    Validates that the generated strategy aligns with user sentiment.
    Prevents bullish beliefs from generating bearish/neutral strategies.
    """
    
    strategy_type = strategy_data.get('type', '').lower()
    trade_legs = strategy_data.get('trade_legs', [])
    
    # Define strategy sentiment mappings
    bullish_strategies = ['call option', 'long call', 'bull call spread', 'bull put spread']
    bearish_strategies = ['put option', 'long put', 'bear call spread', 'bear put spread']
    neutral_strategies = ['iron condor', 'iron butterfly', 'straddle', 'strangle']
    
    # Check for direct sentiment misalignment
    if detected_sentiment == 'bullish':
        if any(bearish in strategy_type for bearish in bearish_strategies):
            print(f"❌ VALIDATION FAILED: Bullish belief '{user_belief}' generated bearish strategy '{strategy_type}'")
            return False
        if any(neutral in strategy_type for neutral in neutral_strategies):
            print(f"❌ VALIDATION FAILED: Bullish belief '{user_belief}' generated neutral strategy '{strategy_type}'")
            return False
    
    elif detected_sentiment == 'bearish':
        if any(bullish in strategy_type for bullish in bullish_strategies):
            print(f"❌ VALIDATION FAILED: Bearish belief '{user_belief}' generated bullish strategy '{strategy_type}'")
            return False
    
    # Check trade legs for option types
    for leg in trade_legs:
        option_type = leg.get('option_type', '').lower()
        if detected_sentiment == 'bullish' and option_type == 'put':
            print(f"❌ VALIDATION FAILED: Bullish belief with put options")
            return False
        elif detected_sentiment == 'bearish' and option_type == 'call':
            print(f"❌ VALIDATION FAILED: Bearish belief with call options")
            return False
    
    print(f"✅ VALIDATION PASSED: {detected_sentiment} belief aligned with {strategy_type}")
    return True


def generate_strategy_with_validation(belief: str, detected_sentiment: str) -> Optional[dict]:
    """
    Enhanced strategy generation with strict sentiment validation.
    Replaces the existing generate_strategy_with_gpt4 function.
    """
    
    try:
        # Get GPT-4 strategy response
        gpt_response = generate_strategy_with_gpt4(belief)
        
        if not gpt_response:
            print("❌ GPT-4 failed to generate strategy")
            return None
        
        # CRITICAL: Validate sentiment alignment
        if not validate_strategy_sentiment_alignment(gpt_response, belief, detected_sentiment):
            print(f"🚫 BLOCKING MISALIGNED STRATEGY: {gpt_response.get('type', 'Unknown')}")
            return None
        
        print(f"✅ VALIDATED STRATEGY: {gpt_response.get('type', 'Unknown')} for {detected_sentiment} sentiment")
        return gpt_response
        
    except Exception as e:
        print(f"❌ Strategy generation error: {str(e)}")
        return None       