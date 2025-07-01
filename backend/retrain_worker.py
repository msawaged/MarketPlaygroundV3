# backend/retrain_worker.py
# ✅ Background worker: Retrains models automatically when enough new feedback is collected

import time
import os
import json
import pandas as pd
from datetime import datetime

from backend.train_all_models import train_all_models  # Master training function
from backend.utils.logger import write_training_log     # Log summary for frontend

# === Paths & Config ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")  # Full retrain history
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")  # Tracks last retrain state
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")  # Global feedback log

FEEDBACK_THRESHOLD = 25  # Minimum new feedback entries before retraining

# === Helper: Write to retrain log file ===
def log_to_file(message: str):
    with open(LOG_PATH, "a") as f:
        f.write(message + "\n")
    print(message)

# === Load previous retrain count (from JSON) ===
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
            "timestamp": datetime.now().isoformat()
        }, f)

# === Read current feedback row count ===
def get_feedback_count():
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception as e:
        log_to_file(f"❌ Error reading feedback.csv: {str(e)}")
        return 0

# === MAIN LOOP ===
def run_retraining_loop(interval: int = 3600):
    """
    Infinite loop that checks for enough new feedback and retrains when ready.
    Called by Render background worker automatically.
    """
    while True:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        try:
            current_count = get_feedback_count()
            last_count = load_last_retrain_count()
            new_entries = current_count - last_count

            log_to_file(f"\n🧠 [{timestamp}] Checking feedback growth...")
            log_to_file(f"→ Feedback count: {current_count}, Last retrain: {last_count}, New since: {new_entries}")

            if new_entries >= FEEDBACK_THRESHOLD:
                log_to_file("⚙️ Triggering model retraining...")
                train_all_models()
                save_retrain_state(current_count)
                log_to_file("✅ Retraining complete. Saved new feedback count.\n")
                write_training_log("✅ Models retrained from retrain_worker.py")
            else:
                log_to_file(f"⏭️ Not enough feedback yet (need {FEEDBACK_THRESHOLD}, have {new_entries})\n")

        except Exception as e:
            log_to_file(f"❌ Error during retrain cycle: {str(e)}\n")

        log_to_file(f"⏳ Sleeping {interval} seconds before next check...\n")
        time.sleep(interval)

# === ENTRY POINT ===
if __name__ == "__main__":
    run_retraining_loop()
