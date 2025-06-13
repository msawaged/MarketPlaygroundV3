# main.py
# Entry point for MarketPlayground AI Engine

from ai_engine import run_ai_engine                 # Parses belief into base output
from payoff_plotter import plot_payoff              # Visualizes the strategy payoff

if __name__ == "__main__":
    print("\nWelcome to MarketPlayground AI Engine 🧠")
    belief = input("Enter your market belief: ").strip()

    # Parse belief and get strategy
    parsed, strategy = run_ai_engine(belief)

    # Debug output
    print("\n[DEBUG] AI Engine Output:")
    print(parsed, strategy)

    # Extract key values from parsed and strategy
    ticker = parsed.get("ticker", "")
    tags = parsed.get("tags", {})
    legs = strategy.get("legs", [])
    expiry = strategy.get("expiry", "N/A")
    payout = strategy.get("payout", "N/A")

    # Final display
    print("\nSuggested Strategy:")
    print(f"Ticker: {ticker}")
    print(f"Tags: {tags}")
    print(f"Type: {strategy['type']}")
    print(f"Legs: {legs}")
    print(f"Expiry: {expiry}")
    print(f"Payout: {payout}")

    # Plot payoff chart
    print("\n📈 Generating payoff chart...")
    plot_payoff(ticker, legs)
