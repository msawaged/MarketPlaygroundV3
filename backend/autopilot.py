# autopilot.py
import time
from ai_engine import run_ai_engine
from payoff_plotter import plot_payoff
import random

# A pool of tickers, phrases, durations, and volatility words
tickers = ["AAPL", "TSLA", "GOOGL", "META", "SPY", "QQQ", "BTC", "ETH", "OIL", "GOLD"]
verbs = ["will rally", "might dump", "could trade flat", "is going to explode", "is crashing"]
times = ["today", "tomorrow", "this week", "next month", "this quarter", "next year"]

def generate_belief():
    return f"{random.choice(tickers)} {random.choice(verbs)} {random.choice(times)}"

while True:
    belief = generate_belief()
    print(f"\n🧠 Auto-Belief: {belief}")
    
    try:
        parsed, strategy = run_ai_engine(belief)
        print("[✅] Output:")
        print(parsed)
        print(strategy)

        # Optional: Visualize
        ticker = parsed.get("ticker", "")
        legs = strategy.get("legs", [])
        plot_payoff(ticker, legs)

    except Exception as e:
        print(f"[❌] Error processing belief: {e}")

    time.sleep(10)  # Wait 10 seconds before next belief
