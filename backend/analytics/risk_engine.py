# backend/analytics/risk_engine.py

"""
Analyzes logged equity performance to calculate:
- Daily returns
- Max drawdown
- Volatility
- Risk profile label
"""

import os
import json
import numpy as np
from typing import Dict

PNL_PATH = os.path.join("backend", "pnl.json")

def calculate_risk_metrics() -> Dict[str, float]:
    """
    Returns volatility, max drawdown, and risk label.
    """
    if not os.path.exists(PNL_PATH):
        return {"error": "pnl.json not found"}

    with open(PNL_PATH, "r") as f:
        data = json.load(f)

    equity_series = [entry["equity"] for entry in data]
    if len(equity_series) < 2:
        return {"error": "Not enough data"}

    # Daily returns
    returns = np.diff(equity_series) / equity_series[:-1]
    volatility = float(np.std(returns))

    # Max drawdown
    peak = equity_series[0]
    max_dd = 0
    for value in equity_series:
        peak = max(peak, value)
        dd = (peak - value) / peak
        max_dd = max(max_dd, dd)

    # Risk label
    if max_dd < 0.05 and volatility < 0.01:
        label = "Low"
    elif max_dd < 0.15 and volatility < 0.03:
        label = "Moderate"
    else:
        label = "High"

    return {
        "volatility": round(volatility, 4),
        "max_drawdown": round(max_dd, 4),
        "risk_profile": label
    }
