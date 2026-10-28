# backend/test_validator.py

from strategy_validator import evaluate_strategy_against_belief

# === Example Belief and Strategy ===
belief = "TSLA will go up 10% in the next two weeks"

strategy = {
    "type": "long call",
    "trade_legs": ["Buy 1 call 350 strike"],
    "price": 320.00,  # current price
    "expiration": "2024-08-01"
}

# === Run the evaluation ===
result = evaluate_strategy_against_belief(belief, strategy)

# === Print the result ===
print("💡 Evaluation Result:")
for key, value in result.items():
    print(f"{key}: {value}")
