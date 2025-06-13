# refiner.py
# 🛠️ Adjusts a base strategy to be safer or more aggressive

def prompt_user_for_refinement(strategy, preference):
    """
    Modifies the original strategy based on user preference.
    """
    if not strategy.get("legs"):
        return strategy

    refined_legs = []
    for leg in strategy["legs"]:
        if preference == "more aggressive":
            refined_legs.append(leg.replace("ATM", "slightly OTM"))
        elif preference == "safer":
            refined_legs.append(leg.replace("ATM", "slightly ITM"))
        else:
            refined_legs.append(leg)

    return {
        "type": strategy["type"] + " (Refined)",
        "legs": refined_legs,
        "expiry": strategy.get("expiry", ""),
        "payout": strategy.get("payout", "")
    }
