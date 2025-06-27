# scripts/generate_clean_training_data.py

"""
This script generates clean training CSVs from feedback_data.json:
- clean_belief_tags.csv
- clean_belief_strategy.csv
- clean_belief_asset.csv

Saved to: backend/training_data/
"""

import json
import csv
from pathlib import Path

# === Paths ===
feedback_file = Path("backend/feedback_data.json")
output_dir = Path("backend/training_data")
output_dir.mkdir(parents=True, exist_ok=True)

# === Load data ===
with feedback_file.open("r") as f:
    data = json.load(f)

# === Initialize CSV rows ===
tags_rows = [("belief", "tag")]
strategy_rows = [("belief", "strategy")]
asset_rows = [("belief", "asset_class")]

# === Extract data ===
for entry in data:
    belief = entry.get("belief", "").strip()
    feedback = entry.get("result", "").strip().lower()  # fixed: should be 'result'
    strategy_obj = entry.get("strategy", {})

    if not belief or feedback != "good" or not isinstance(strategy_obj, dict):
        continue

    strategy_type = strategy_obj.get("type", "").strip()
    asset_class = strategy_obj.get("asset_class", "").strip()

    # Fallback if asset_class missing
    if not asset_class:
        strategy_type_lc = strategy_type.lower()
        if "bond" in strategy_type_lc:
            asset_class = "bonds"
        elif "commodity" in strategy_type_lc:
            asset_class = "commodity"
        elif "stock" in strategy_type_lc:
            asset_class = "stock"
        elif "etf" in strategy_type_lc:
            asset_class = "etf"
        elif "crypto" in strategy_type_lc:
            asset_class = "crypto"
        else:
            asset_class = "options"  # default fallback

    tags_rows.append((belief, strategy_type.lower()))
    strategy_rows.append((belief, strategy_type))
    asset_rows.append((belief, asset_class.lower()))

# === Save CSVs ===
def save_csv(path: Path, rows):
    with path.open("w", newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

save_csv(output_dir / "clean_belief_tags.csv", tags_rows)
save_csv(output_dir / "clean_belief_strategy.csv", strategy_rows)
save_csv(output_dir / "clean_belief_asset.csv", asset_rows)

print("✅ CSVs generated and saved to backend/training_data:")
print("- clean_belief_tags.csv")
print("- clean_belief_strategy.csv")
print("- clean_belief_asset.csv")
