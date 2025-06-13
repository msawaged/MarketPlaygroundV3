# payoff_plotter.py
# Visualizes the payoff diagram for a given options strategy

import matplotlib.pyplot as plt
import numpy as np

def plot_payoff(ticker, legs):
    """
    Generates a simple payoff chart based on the given strategy legs.

    Args:
        ticker (str): Underlying asset ticker
        legs (list): List of strategy leg descriptions
    """

    print(f"\n📊 Plotting payoff for {ticker}...")

    # Simulate prices around current value
    current_price = 100  # This can be pulled from real-time data later
    price_range = np.linspace(current_price * 0.8, current_price * 1.2, 100)
    payoff = np.zeros_like(price_range)

    for leg in legs:
        if "Buy" in leg and "call" in leg:
            strike = current_price * 1.05
            payoff += np.maximum(price_range - strike, 0)
        elif "Sell" in leg and "call" in leg:
            strike = current_price * 1.10
            payoff -= np.maximum(price_range - strike, 0)
        elif "Buy" in leg and "put" in leg:
            strike = current_price * 0.95
            payoff += np.maximum(strike - price_range, 0)
        elif "Sell" in leg and "put" in leg:
            strike = current_price * 0.90
            payoff -= np.maximum(strike - price_range, 0)

    plt.figure(figsize=(8, 5))
    plt.plot(price_range, payoff, label="Payoff")
    plt.axhline(0, color='gray', linestyle='--')
    plt.title(f"{ticker} Strategy Payoff")
    plt.xlabel("Underlying Price")
    plt.ylabel("Profit/Loss")
    plt.grid(True)
    plt.legend()
    plt.show()
