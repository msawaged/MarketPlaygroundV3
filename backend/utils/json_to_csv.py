# ✅ File: backend/utils/json_to_csv.py
# Converts feedback_data.json → feedback.csv for retraining
# Extracts only the strategy description and feedback label

import json
import csv
import os

# Define paths
json_path = os.path.join("backend", "feedback_data.json")
csv_path = os.path.join("backend", "feedback.csv")

# Load JSON data
with open(json_path, "r") as infile:
    data = json.load(infile)

# Flatten data into simple rows
flattened = []
for entry in data:
    try:
        strategy_text = entry["strategy"]["description"]
        label = 1 if entry["feedback"].strip().lower() == "good" else 0
        flattened.append({"strategy": strategy_text, "label": label})
    except Exception as e:
        print(f"⚠️ Skipped invalid entry: {e}")

# Write to CSV
with open(csv_path, "w", newline="") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["strategy", "label"])
    writer.writeheader()
    writer.writerows(flattened)

print(f"✅ Created: {csv_path} with {len(flattened)} rows.")
