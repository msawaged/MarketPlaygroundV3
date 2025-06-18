# backend/feedback_handler.py

import json
import os

FEEDBACK_FILE = "backend/feedback_data.json"

def save_feedback_entry(belief, strategy, feedback):
    """
    Save a feedback entry as a JSON object to backend/feedback_data.json.
    If the file doesn't exist, it creates one.
    """
    entry = {
        "belief": belief,
        "strategy": strategy,
        "feedback": feedback
    }

    # Load existing data if file exists
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []

    # Append and save
    data.append(entry)
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"[feedback_handler] ✅ Feedback saved: {entry}")
