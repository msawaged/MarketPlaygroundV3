#!/usr/bin/env python3
"""
SENTIMENT VALIDATION FIX TEST
Tests the repaired sentiment validation logic to ensure bullish beliefs generate bullish strategies.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_engine.gpt4_strategy_generator import generate_strategy_with_validation
from belief_parser import parse_belief

# Set up environment for OpenAI
os.environ.setdefault('OPENAI_API_KEY', 'your-key-here')  # Will be overridden by actual key

def test_sentiment_fix():
    """Test that bullish beliefs generate bullish strategies after fix."""
    
    test_cases = [
        {
            "belief": "Tesla will rally to 200",
            "expected_sentiment": "bullish",
            "invalid_strategies": ["straddle", "strangle", "iron condor", "long put", "bear put spread"]
        },
        {
            "belief": "Bitcoin will hit 100k soon", 
            "expected_sentiment": "bullish",
            "invalid_strategies": ["straddle", "strangle", "iron condor", "long put", "bear put spread"]
        },
        {
            "belief": "NVDA going to moon",
            "expected_sentiment": "bullish", 
            "invalid_strategies": ["straddle", "strangle", "iron condor", "long put", "bear put spread"]
        },
        {
            "belief": "Gold will crash hard",
            "expected_sentiment": "bearish",
            "invalid_strategies": ["straddle", "strangle", "iron condor", "long call", "bull call spread"] 
        }
    ]
    
    results = []
    
    print("🧪 TESTING SENTIMENT VALIDATION FIX")
    print("=" * 50)
    
    for i, test in enumerate(test_cases, 1):
        belief = test["belief"]
        expected = test["expected_sentiment"]
        invalid = test["invalid_strategies"]
        
        print(f"\nTest {i}: {belief}")
        print(f"Expected sentiment: {expected}")
        
        # Parse belief to get detected sentiment
        parsed = parse_belief(belief)
        detected_sentiment = parsed.get("direction")
        
        print(f"Detected sentiment: {detected_sentiment}")
        
        # Test strategy generation with validation
        try:
            strategy = generate_strategy_with_validation(belief, detected_sentiment)
            
            if not strategy:
                print("❌ BLOCKED: Strategy was correctly blocked (if misaligned)")
                results.append({
                    "test": i,
                    "belief": belief,
                    "status": "BLOCKED",
                    "strategy_type": None,
                    "alignment": "N/A"
                })
                continue
            
            strategy_type = strategy.get("type", "Unknown").lower()
            print(f"Generated strategy: {strategy_type}")
            
            # Check if strategy is invalid for sentiment
            is_misaligned = any(inv in strategy_type for inv in invalid)
            
            if is_misaligned:
                print(f"❌ FAIL: Generated {strategy_type} for {expected} belief")
                results.append({
                    "test": i,
                    "belief": belief,
                    "status": "FAIL",
                    "strategy_type": strategy_type,
                    "alignment": "MISALIGNED"
                })
            else:
                print(f"✅ PASS: {strategy_type} aligns with {expected} sentiment")
                results.append({
                    "test": i,
                    "belief": belief,
                    "status": "PASS", 
                    "strategy_type": strategy_type,
                    "alignment": "ALIGNED"
                })
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "test": i,
                "belief": belief,
                "status": "ERROR",
                "strategy_type": None,
                "alignment": str(e)
            })
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    blocked = sum(1 for r in results if r["status"] == "BLOCKED")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    
    print(f"Total tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"🚫 Blocked (expected): {blocked}")
    print(f"❌ Failed: {failed}")
    print(f"🔥 Errors: {errors}")
    
    success_rate = ((passed + blocked) / total * 100) if total > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if success_rate >= 75:
        print("🎉 SENTIMENT FIX SUCCESSFUL!")
    else:
        print("⚠️ SENTIMENT FIX NEEDS MORE WORK")
    
    return results

if __name__ == "__main__":
    test_sentiment_fix()