# backend/test_ai_engine.py

"""
This script tests the AI engine by feeding it sample beliefs
and printing out the full parsed output and strategy recommendation.
"""

import sys
import os
sys.path.append(os.path.abspath("."))  # ✅ Add current dir to path so relative imports work

from ai_engine.ai_engine import run_ai_engine  # ✅ Relative import works now

# Define test beliefs and risk profiles
test_cases = [
    ("I think AAPL will go up next week", "moderate"),
    ("TSLA is going to crash hard", "aggressive"),
    ("I want to double my money on NVDA", "aggressive"),
    ("The market will tank on Monday", "moderate"),
    ("I believe the bond market is safe", "conservative"),
    ("Buy energy stocks for a strong summer", "moderate"),
    ("Gold prices will rise due to inflation", "moderate"),
    ("I'm worried about tech volatility", "conservative"),
]

# Loop through and test each case
print("\n================= AI Engine Test =================\n")

for i, (belief, profile) in enumerate(test_cases, start=1):
    print(f"\n🚀 Test Case {i}")
    print(f"Belief: {belief}")
    print(f"Risk Profile: {profile}")

    try:
        output = run_ai_engine(belief, risk_profile=profile, user_id="test_user")
        print("🎯 Strategy Output:")
        for key, value in output.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"❌ Error during processing: {e}")

print("\n✅ All test cases processed.\n")
