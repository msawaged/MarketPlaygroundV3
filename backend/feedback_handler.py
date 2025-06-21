# feedback_handler.py
# This module supports both CSV and JSON logging for feedback tracking.

import csv
import os
import json
from datetime import datetime

CSV_FEEDBACK_FILE = "backend/feedback.csv"
JSON_FEEDBACK_FILE = "backend/feedback_data.json"

def save_feedback(belief: str, strategy: str, result: str):
    """
    Logs feedback to a CSV file. This is used for training the CSV-based model later.

    Args:
        belief (str): The user's original belief.
        strategy (str): The selected strategy.
        result (str): The feedback label (e.g., "positive", "missed", "bad").
    """
    try:
        with open(CSV_FEEDBACK_FILE, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([belief, strategy, result])
        print(f"[✓] CSV feedback saved: {belief}, {strategy}, {result}")
    except Exception as e:
        print(f"[ERROR] Failed to save CSV feedback: {e}")

def log_feedback(belief: str, strategy: str, result: str):
    """
    Logs feedback to a JSON file, used for future AI training and tracking history.

    Args:
        belief (str): The user's original belief.
        strategy (str): The full strategy generated.
        result (str): The user feedback result.
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "belief": belief,
        "strategy": strategy,
        "result": result
    }

    # Load existing data
    if os.path.exists(JSON_FEEDBACK_FILE):
        with open(JSON_FEEDBACK_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []

    data.append(entry)

    try:
        with open(JSON_FEEDBACK_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[✓] JSON feedback logged for belief: '{belief}'")
    except Exception as e:
        print(f"[ERROR] Failed to write JSON feedback: {e}")
