#!/usr/bin/env python3
import csv
import random

STRATEGIES = ["bull call spread", "bear put spread", "iron condor", "straddle", "long crypto", "long futures", "short bond ladder", "long forex eur/usd", "covered call", "protective put", "collar", "butterfly spread"]

BELIEF_TEMPLATES = [
    ("Tech stocks will rally", ["bull call spread", "long crypto", "covered call"]),
    ("Market crash incoming", ["bear put spread", "protective put", "collar"]),
    ("High volatility expected", ["straddle", "iron condor"]),
    ("Fed will cut rates", ["long futures", "bull call spread", "long crypto"]),
    ("Recession fears growing", ["bear put spread", "protective put"]),
    ("Market will stay flat", ["iron condor", "butterfly spread"]),
    ("AI stocks undervalued", ["bull call spread", "long crypto"]),
    ("Dollar will weaken", ["long forex eur/usd", "long crypto"]),
    ("Energy will outperform", ["bull call spread", "long futures"]),
    ("Crypto adoption accelerating", ["long crypto", "bull call spread"])
]

def generate_data(n=150):
    data = []
    for _ in range(n):
        belief_template, strategies = random.choice(BELIEF_TEMPLATES)
        belief = random.choice([belief_template, f"I believe {belief_template.lower()}", f"Expecting {belief_template.lower()}"])
        strategy = random.choice(strategies)
        asset = random.choice(["options", "crypto", "futures", "stocks", "bonds", "forex"])
        data.append([belief, strategy, asset])
    return data

if __name__ == "__main__":
    data = generate_data(150)
    with open("../strategy_outcomes.csv", "a", newline="") as f:
        csv.writer(f).writerows(data)
    print(f"✅ Added {len(data)} samples")
