# backend/retrain_worker.py
# ✅ Background worker: Auto-retrains models when enough new feedback is collected
# ✅ Now also logs to Supabase via write_training_log()

import time
import os
import json
import pandas as pd
from datetime import datetime

from backend.train_all_models import train_all_models  # Full model retraining pipeline
from backend.utils.logger import write_training_log     # Unified logger (Supabase + local)

# === Path Setup ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)  # Auto-create if missing

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")           # Full retrain loop log
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")   # Stores last feedback count
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")           # Source of truth for retraining

FEEDBACK_THRESHOLD = 25  # 🔁 Retrain only if this many new feedback rows appear

# === Logging Helper ===
def log_to_file(message: str):
    """Logs message to local file, console, and Supabase table."""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}] {message}"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"❌ Logging failed: {str(e)}")
    print(line)

    # ✅ Supabase + JSON + plain text log in unified logger
    write_training_log(message, source="retrain_worker")

# === Feedback Count Tracking ===
def get_feedback_count() -> int:
    """Returns the current row count of feedback.csv (or 0 on error)."""
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception as e:
        log_to_file(f"❌ Failed to read feedback.csv: {str(e)}")
        return 0

def load_last_retrain_count() -> int:
    """Loads feedback count from last retraining run."""
    if os.path.exists(LAST_RETRAIN_PATH):
        with open(LAST_RETRAIN_PATH, "r") as f:
            return json.load(f).get("feedback_count", 0)
    return 0

def save_retrain_state(current_count: int):
    """Persists latest retrain state to JSON."""
    with open(LAST_RETRAIN_PATH, "w") as f:
        json.dump({
            "feedback_count": current_count,
            "timestamp": datetime.utcnow().isoformat()
        }, f)

# === Background Loop ===
def run_retraining_loop(interval: int = 3600):
    """
    Main worker loop:
    - Checks feedback.csv row count
    - Retrains models if threshold is met
    - Logs every step (Render log + Supabase + /debug visibility)
    """
    log_to_file("🚨 Retrain worker started (Render background process)")
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
            log_to_file(f"❌ Error in retraining loop: {str(e)}")

        log_to_file(f"⏳ Sleeping {interval} seconds until next check...\n")
        time.sleep(interval)

# === Entry Point ===
if __name__ == "__main__":
    run_retraining_loop()
