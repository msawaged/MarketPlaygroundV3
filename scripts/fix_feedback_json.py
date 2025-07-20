# scripts/fix_feedback_json.py

"""
This script scans the feedback_data.json file and upgrades all flat strategy strings
(e.g., "Long Put") into structured strategy dictionaries with "type", "legs", and "asset_class".
"""

import json
from pathlib import Path

# Path to the original feedback file
feedback_file = Path("backend/feedback_data.json")

# Load the data
with feedback_file.open("r") as f:
    data = json.load(f)

updated = 0
for entry in data:
    strategy = entry.get("strategy")
    if isinstance(strategy, str):
        # Convert flat string to structured strategy object
        entry["strategy"] = {
            "type": strategy,
            "legs": [],
            "asset_class": "options" if "Option" in strategy or "Put" in strategy or "Call" in strategy else "stocks"
        }
        updated += 1

# Save the fixed version
with feedback_file.open("w") as f:
    json.dump(data, f, indent=2)

print(f"✅ Fixed {updated} entries with flat strategy strings.")
print(f"📁 Saved to {feedback_file.resolve()}")
