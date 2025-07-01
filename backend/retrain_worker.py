# backend/retrain_worker.py
# ✅ Reliable background worker: retrains models & writes logs for Render debug

import time
import os
import json
import pandas as pd
from datetime import datetime

from backend.train_all_models import train_all_models
from backend.utils.logger import write_training_log

# === Absolute Path Setup ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")

FEEDBACK_THRESHOLD = 25  # Minimum new feedback rows to trigger retraining

# === Logging ===
def log_to_file(message: str):
    """Append message to retrain_worker.log and print to console."""
    timestamped = f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(timestamped + "\n")
    except Exception as e:
        print(f"❌ Failed to write to log: {e}")
    print(timestamped)

# === Load previous state ===
def load_last_retrain_count():
    if os.path.exists(LAST_RETRAIN_PATH):
        with open(LAST_RETRAIN_PATH, "r") as f:
            return json.load(f).get("feedback_count", 0)
    return 0

# === Save new retrain state ===
def save_retrain_state(current_count):
    with open(LAST_RETRAIN_PATH, "w") as f:
        json.dump({
            "feedback_count": current_count,
            "timestamp": datetime.utcnow().isoformat()
        }, f)

# === Get row count in feedback.csv ===
def get_feedback_count():
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception as e:
        log_to_file(f"❌ Failed to read feedback.csv: {str(e)}")
        return 0

# === Main Retrain Loop ===
def run_retraining_loop(interval: int = 3600):
    while True:
        log_to_file("🔄 Checking feedback for retrain trigger...")
        try:
            current_count = get_feedback_count()
            last_count = load_last_retrain_count()
            new_entries = current_count - last_count

            log_to_file(f"📝 Feedback count = {current_count}, New since last retrain = {new_entries}")

            if new_entries >= FEEDBACK_THRESHOLD:
                log_to_file("⚙️  Enough new feedback — triggering model retraining...")
                train_all_models()
                save_retrain_state(current_count)
                write_training_log("✅ Models retrained from retrain_worker.py")
                log_to_file("✅ Retraining complete and state saved.")
            else:
                log_to_file(f"⏭️  Not enough feedback yet (need {FEEDBACK_THRESHOLD}, have {new_entries})")

        except Exception as e:
            log_to_file(f"❌ Error during retrain check: {str(e)}")

        log_to_file(f"⏳ Sleeping {interval} seconds before next check...\n")
        time.sleep(interval)

# === ENTRY POINT ===
if __name__ == "__main__":
    log_to_file("🚀 Retrain worker started on Render.")
    run_retraining_loop()
