#!/usr/bin/env python3
"""
SENTIMENT VALIDATION LOGIC TEST
Tests only the validation logic without GPT calls to isolate the fix.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_engine.gpt4_strategy_generator import validate_strategy_sentiment_alignment
from belief_parser import parse_belief

def test_validation_logic():
    """Test the sentiment validation logic directly."""
    
    print("🧪 TESTING SENTIMENT VALIDATION LOGIC ONLY")
    print("=" * 50)
    
    # Mock strategies that should be blocked
    test_cases = [
        {
            "belief": "Tesla will rally to 200",
            "detected_sentiment": "bullish",
            "mock_strategy": {
                "type": "Long Straddle",  # SHOULD BE BLOCKED
                "trade_legs": ["buy 1 call", "buy 1 put"],
                "explanation": "Neutral strategy for volatility play"
            },
            "should_pass": False
        },
        {
            "belief": "Bitcoin will hit 100k soon",  
            "detected_sentiment": "bullish",
            "mock_strategy": {
                "type": "Iron Condor",  # SHOULD BE BLOCKED
                "trade_legs": ["sell put", "buy put", "buy call", "sell call"],
                "explanation": "Range-bound neutral strategy"
            },
            "should_pass": False
        },
        {
            "belief": "NVDA going to moon",
            "detected_sentiment": "bullish", 
            "mock_strategy": {
                "type": "Call Option",  # SHOULD PASS
                "trade_legs": ["buy 1 call"],
                "explanation": "Bullish call option strategy"
            },
            "should_pass": True
        },
        {
            "belief": "Gold will crash hard",
            "detected_sentiment": "bearish",
            "mock_strategy": {
                "type": "Straddle",  # SHOULD BE BLOCKED for bearish
                "trade_legs": ["buy 1 call", "buy 1 put"],
                "explanation": "Volatility play with straddle"
            },
            "should_pass": False
        },
        {
            "belief": "Gold will crash hard", 
            "detected_sentiment": "bearish",
            "mock_strategy": {
                "type": "Put Option",  # SHOULD PASS
                "trade_legs": ["buy 1 put"],
                "explanation": "Bearish put option strategy"  
            },
            "should_pass": True
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        belief = test["belief"]
        sentiment = test["detected_sentiment"]
        strategy = test["mock_strategy"]
        should_pass = test["should_pass"]
        
        print(f"\\nTest {i}: {belief}")
        print(f"Sentiment: {sentiment}")
        print(f"Strategy: {strategy['type']}")
        print(f"Expected: {'PASS' if should_pass else 'BLOCK'}")
        
        try:
            validation_result = validate_strategy_sentiment_alignment(
                strategy, belief, sentiment
            )
            
            # Check if validation returned an error (blocked)
            is_blocked = "error" in validation_result
            
            if should_pass and not is_blocked:
                print("✅ CORRECT: Strategy correctly allowed")
                results.append("PASS")
            elif not should_pass and is_blocked:
                print("✅ CORRECT: Strategy correctly blocked")  
                print(f"   Reason: {validation_result.get('message', 'Unknown')}")
                results.append("PASS")
            elif should_pass and is_blocked:
                print("❌ WRONG: Strategy should have passed but was blocked")
                print(f"   Blocked reason: {validation_result.get('message', 'Unknown')}")
                results.append("FAIL")
            else:  # not should_pass and not is_blocked
                print("❌ WRONG: Strategy should have been blocked but passed")
                results.append("FAIL")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append("ERROR")
    
    # Summary
    print("\\n" + "=" * 50)
    print("VALIDATION LOGIC TEST SUMMARY")
    print("=" * 50)
    
    total = len(results)
    passed = results.count("PASS")
    failed = results.count("FAIL") 
    errors = results.count("ERROR")
    
    print(f"Total tests: {total}")
    print(f"✅ Correct: {passed}")
    print(f"❌ Wrong: {failed}")
    print(f"🔥 Errors: {errors}")
    
    success_rate = (passed / total * 100) if total > 0 else 0
    print(f"Validation accuracy: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("🎉 VALIDATION LOGIC IS WORKING CORRECTLY!")
    else:
        print("⚠️ VALIDATION LOGIC NEEDS FIXES")
    
    return results

if __name__ == "__main__":
    test_validation_logic()