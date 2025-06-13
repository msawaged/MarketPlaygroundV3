# payoff_plotter.py

import matplotlib.pyplot as plt
import numpy as np

def plot_payoff(ticker, legs, spot_price=100):
    """
    Simulates and plots a payoff diagram from a list of human-readable option legs.
    """

    print(f"\n📊 Plotting payoff for {ticker}...")

    # Simulated strike reference based on descriptions
    strike_map = {
        "ATM": spot_price,
        "higher": spot_price + 10,
        "even-higher": spot_price + 20,
        "lower": spot_price - 10,
        "even-lower": spot_price - 20
    }

    parsed_legs = []
    for leg in legs:
        parts = leg.lower().split()
        action = parts[0]      # Buy or Sell
        direction = parts[-1]  # Call or Put
        if "even-" in leg:
            strike_desc = "even-" + parts[-2].replace("even-", "")
        else:
            strike_desc = parts[-2]

        strike = strike_map.get(strike_desc, spot_price)
        parsed_legs.append((action, direction, strike))

    # Price range for chart
    price_range = np.linspace(spot_price - 50, spot_price + 50, 200)
    total_payoff = np.zeros_like(price_range)

    # Calculate total payoff
    for action, opt_type, strike in parsed_legs:
        payoff = np.zeros_like(price_range)
        if opt_type == "call":
            payoff = np.maximum(price_range - strike, 0)
        elif opt_type == "put":
            payoff = np.maximum(strike - price_range, 0)

        if action == "sell":
            payoff *= -1

        total_payoff += payoff

    # Plotting
    plt.figure()
    plt.plot(price_range, total_payoff, label="Payoff")
    plt.axhline(0, color='gray', linestyle='--')
    plt.title(f"{ticker} Strategy Payoff")
    plt.xlabel("Price at Expiration")
    plt.ylabel("Profit / Loss")
    plt.grid(True)
    plt.legend()
    plt.show()
