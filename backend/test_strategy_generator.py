# backend/test_strategy_generator.py

from backend.ai_engine.ai_engine import generate_trading_strategy

test_belief = "The Japanese yen will weaken against the dollar"
test_user_id = "unit_test_gpt_to_ml"

response = generate_trading_strategy(test_belief, user_id=test_user_id)

print("\n🎯 TEST OUTPUT:\n")
print(response)
