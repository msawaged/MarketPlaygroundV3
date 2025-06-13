import pandas as pd
import random

beliefs = [
    "TSLA is going to explode this week",
    "AAPL will fall hard tomorrow",
    "NVDA might stay flat",
    "SPY will rally next month",
    "QQQ is overbought short term",
    "Gold is stable now",
    "Oil prices will surge soon",
    "Bitcoin is crashing",
    "The market will be choppy",
    "Interest rates will stay steady"
]

directions = ["bullish", "bearish", "neutral"]
durations = ["short", "medium", "long"]
volatilities = ["low", "medium", "high"]

synthetic_data = []

for _ in range(100):  # generate 100 samples
    belief = random.choice(beliefs)
    direction = random.choice(directions)
    duration = random.choice(durations)
    volatility = random.choice(volatilities)
    synthetic_data.append({
        "belief_text": belief,
        "direction": direction,
        "duration": duration,
        "volatility": volatility
    })

df = pd.DataFrame(synthetic_data)
df.to_csv("belief_data.csv", index=False)
print("✅ Generated 100 synthetic beliefs into belief_data.csv")
