# backend/retrain_worker.py
# ✅ Background worker: Auto-retrains models when enough new feedback is collected
# ✅ Logs to Supabase + retrain_worker.log + last_retrain.json

import time
import os
import json
import pandas as pd
from datetime import datetime

from backend.train_all_models import train_all_models  # Full retraining pipeline
from backend.utils.logger import write_training_log    # Logs to Supabase + local

# === Path Setup ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")

FEEDBACK_THRESHOLD = 5  # ✅ Trigger retrain only if this many new feedback rows exist

# === Logging Helper ===
def log_to_file(message: str):
    """Logs message to log file, console, and Supabase."""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    full = f"[{timestamp}] {message}"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(full + "\n")
    except Exception as e:
        print(f"❌ File logging failed: {str(e)}")
    print(full)
    write_training_log(message, source="retrain_worker")

# === Feedback Tracking ===
def get_feedback_count() -> int:
    """Returns row count of feedback.csv (or 0 on error)."""
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception as e:
        log_to_file(f"❌ Failed to read feedback.csv: {str(e)}")
        return 0

def load_last_retrain_count() -> int:
    """Returns feedback count from last retrain (stored in JSON)."""
    if os.path.exists(LAST_RETRAIN_PATH):
        try:
            with open(LAST_RETRAIN_PATH, "r") as f:
                return json.load(f).get("feedback_count", 0)
        except Exception:
            return 0
    return 0

def save_retrain_state(current_count: int):
    """Persists new retrain state to JSON."""
    with open(LAST_RETRAIN_PATH, "w") as f:
        json.dump({
            "feedback_count": current_count,
            "timestamp": datetime.utcnow().isoformat()
        }, f)

# === Main Worker Loop ===
def run_retraining_loop(interval: int = 3600):
    """
    Infinite loop that:
    - Checks feedback.csv count
    - Retrains if threshold is hit
    - Logs every step
    """
    log_to_file("🚨 Retrain worker started")
    while True:
        try:
            current_count = get_feedback_count()
            last_count = load_last_retrain_count()
            new_entries = current_count - last_count

            log_to_file(f"🧠 Feedback: {current_count} total | {new_entries} new since last retrain")

            if new_entries >= FEEDBACK_THRESHOLD:
                log_to_file("⚙️  Retraining triggered...")
                train_all_models()
                save_retrain_state(current_count)
                log_to_file("✅ Model retraining completed")
            else:
                log_to_file(f"⏭️  Skipped — Need {FEEDBACK_THRESHOLD}, got {new_entries}")

        except Exception as e:
            log_to_file(f"❌ Error: {str(e)}")

        log_to_file(f"⏳ Sleeping {interval} seconds...\n")
        time.sleep(interval)

# === Entrypoint ===
if __name__ == "__main__":
    run_retraining_loop()
