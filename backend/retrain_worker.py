# backend/retrain_worker.py
# ✅ Smarter background worker: Only retrains when enough new feedback exists

import time
import os
import json
import pandas as pd
from datetime import datetime

# ✅ Import the main training pipeline
from backend.train_all_models import train_all_models

# ✅ Log + timestamp files
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")

# ✅ Feedback file location
FEEDBACK_PATH = os.path.join(os.path.dirname(__file__), "feedback.csv")

# ✅ Configurable threshold
FEEDBACK_THRESHOLD = 25  # Only retrain if at least this many new entries

def log_to_file(message: str):
    """Appends a timestamped message to the retrain_worker.log file."""
    with open(LOG_PATH, "a") as f:
        f.write(message + "\n")
    print(message)

def load_last_retrain_count():
    """Returns the feedback count from the last retrain."""
    if os.path.exists(LAST_RETRAIN_PATH):
        with open(LAST_RETRAIN_PATH, "r") as f:
            return json.load(f).get("feedback_count", 0)
    return 0

def save_retrain_state(current_count):
    """Saves the latest feedback count after successful retraining."""
    with open(LAST_RETRAIN_PATH, "w") as f:
        json.dump({
            "feedback_count": current_count,
            "timestamp": datetime.now().isoformat()
        }, f)

def get_feedback_count():
    """Returns the number of feedback entries in feedback.csv."""
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception:
        return 0

def run_retraining_loop(interval: int = 3600):
    """
    Infinite loop that checks feedback growth and retrains only if needed.
    Logs all decisions and results.
    """
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            current_count = get_feedback_count()
            last_count = load_last_retrain_count()
            new_entries = current_count - last_count

            log_to_file(f"\n🧠 [{timestamp}] Checking for new feedback...")
            log_to_file(f"→ Current: {current_count}, Last Retrain: {last_count}, New: {new_entries}")

            if new_entries >= FEEDBACK_THRESHOLD:
                log_to_file(f"⚙️  Enough new feedback! Starting retraining...")

                train_all_models()

                save_retrain_state(current_count)
                log_to_file(f"✅ Retraining complete. Updated count saved.\n")
                        from backend.utils.logger import write_training_log  # ✅ Add at the top of the file

...

save_retrain_state(current_count)
log_to_file(f"✅ Retraining complete. Updated count saved.\n")
write_training_log("✅ Models retrained from background worker.")

            else:
                log_to_file(f"⏭️  Not enough new feedback to retrain (need {FEEDBACK_THRESHOLD}, have {new_entries}).\n")

        except Exception as e:
            log_to_file(f"❌ Error during retraining check: {str(e)}\n")

        log_to_file(f"⏳ Sleeping {interval} seconds until next check...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_retraining_loop()
