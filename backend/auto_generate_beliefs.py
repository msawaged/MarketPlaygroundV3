# auto_generate_beliefs.py
import random
import csv
import time

TICKERS = ["AAPL", "TSLA", "SPY", "QQQ", "GOOGL", "AMZN", "META", "BTC", "ETH", "GOLD", "OIL"]
ACTIONS = [
    "will go up", "is going to crash", "will trade sideways", "might rally",
    "could drop", "will explode", "will dump", "is stable", "will bounce",
    "looks volatile", "will trade flat"
]
TIMINGS = ["tomorrow", "next week", "this month", "today", "soon", "next quarter"]

DIRECTIONS = {"up": "bullish", "rally": "bullish", "explode": "bullish", "bounce": "bullish",
              "crash": "bearish", "drop": "bearish", "dump": "bearish",
              "sideways": "neutral", "stable": "neutral", "flat": "neutral", "volatile": "neutral"}

DURATION_TAGS = {"tomorrow": "short", "today": "short", "next week": "short",
                 "this month": "medium", "soon": "medium", "next quarter": "long"}

VOLATILITY_TAGS = {"explode": "high", "dump": "high", "volatile": "high",
                   "bounce": "medium", "rally": "medium",
                   "flat": "low", "stable": "low", "sideways": "low"}

def infer_tags(action, timing):
    direction = next((v for k, v in DIRECTIONS.items() if k in action), "neutral")
    duration = DURATION_TAGS.get(timing, "medium")
    volatility = next((v for k, v in VOLATILITY_TAGS.items() if k in action), "medium")
    return direction, duration, volatility

def generate_belief():
    ticker = random.choice(TICKERS)
    action = random.choice(ACTIONS)
    timing = random.choice(TIMINGS)
    belief = f"{ticker} {action} {timing}"
    direction, duration, volatility = infer_tags(action, timing)
    return belief, direction, duration, volatility

def save_belief_to_csv(file_path="belief_data.csv"):
    with open(file_path, mode='a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        while True:
            belief, direction, duration, volatility = generate_belief()
            writer.writerow([belief, direction, duration, volatility])
            print(f"📝 {belief} | {direction} | {duration} | {volatility}")
            time.sleep(0.5)  # Generate 2 beliefs per second (adjust as needed)

if __name__ == "__main__":
    print("🚀 Generating beliefs. Press Ctrl+C to stop.")
    save_belief_to_csv()
