# strategy_refiner.py
# Adjusts an options strategy based on user refinement request
# Supports 'more aggressive' and 'safer' refinements

def refine_strategy(current_strategy, request="more aggressive"):
    """
    Takes a strategy and returns a modified version based on refinement request.
    Example requests: 'more aggressive', 'safer'
    """
    legs = current_strategy.get("legs", [])
    new_legs = []
    change = 5  # Strike adjustment in dollars

    # If no legs or shares strategy, skip refinement
    if not legs or "shares" in current_strategy.get("type", "").lower():
        return current_strategy

    for leg in legs:
        try:
            parts = leg.split()  # e.g., ['Buy', 'TSLA', '327.5c', 'exp', '2025-06-13'] or shorter
            action = parts[0]    # 'Buy' or 'Sell'
            ticker = parts[1]
            raw = parts[2]       # e.g., '327.5c' or '330p'
            expiry = f"exp {parts[4]}" if "exp" in leg else ""

            strike = float(raw[:-1])  # extract 327.5 from '327.5c'
            opt_type = raw[-1]        # 'c' or 'p'

            # Adjust strike based on action and refinement request
            if request == "more aggressive":
                strike += change
            elif request == "safer":
                strike -= change

            # Build new leg
            new_leg = f"{action} {ticker} {strike}{opt_type} {expiry}".strip()
            new_legs.append(new_leg)

        except Exception:
            # Fallback to original leg if parsing fails
            new_legs.append(leg)

    return {
        **current_strategy,
        "type": f"{current_strategy['type']} (Refined)",
        "legs": new_legs
    }
