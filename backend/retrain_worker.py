# backend/retrain_worker.py
# ✅ Background worker to auto-retrain all models when enough new feedback is logged
# ✅ Logs training events to local file, Supabase, and tracks retrain state

import time
import os
import json
import pandas as pd
from datetime import datetime

# Import the full retraining pipeline
from backend.train_all_models import train_all_models

# Logging utility that also pushes logs to Supabase
from backend.utils.logger import write_training_log

# === Directory and file path setup ===

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)  # Create the logs directory if it doesn't exist

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")
LAST_RETRAIN_PATH = os.path.join(LOG_DIR, "last_retrain.json")
FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")

# === Threshold configuration ===

# Only retrain when this many new feedback rows are collected
FEEDBACK_THRESHOLD = 5

# === Helper: Log messages ===

def log_to_file(message: str):
    """
    Logs a message with a timestamp to:
    - retrain_worker.log (file)
    - Supabase (via write_training_log)
    - Console
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    full = f"[{timestamp}] {message}"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(full + "\n")
    except Exception as e:
        print(f"❌ File logging failed: {str(e)}")
    print(full)  # Always print to console
    write_training_log(message, source="retrain_worker")

# === Helper: Get current feedback row count ===

def get_feedback_count() -> int:
    """
    Returns the number of rows in feedback.csv.
    If file doesn't exist or can't be read, returns 0.
    """
    if not os.path.exists(FEEDBACK_PATH):
        return 0
    try:
        df = pd.read_csv(FEEDBACK_PATH)
        return len(df)
    except Exception as e:
        log_to_file(f"❌ Failed to read feedback.csv: {str(e)}")
        return 0

# === Helper: Load last saved feedback count ===

def load_last_retrain_count() -> int:
    """
    Loads the last feedback count at the time of the last retrain.
    Used to check how many new rows exist.
    """
    if os.path.exists(LAST_RETRAIN_PATH):
        try:
            with open(LAST_RETRAIN_PATH, "r") as f:
                return json.load(f).get("feedback_count", 0)
        except Exception:
            return 0
    return 0

# === Helper: Save latest retrain state ===

def save_retrain_state(current_count: int):
    """
    Saves the current feedback count and timestamp to last_retrain.json.
    This is used to track whether a retrain is needed later.
    """
    with open(LAST_RETRAIN_PATH, "w") as f:
        json.dump({
            "feedback_count": current_count,
            "timestamp": datetime.utcnow().isoformat()
        }, f)

# === Main Worker Loop ===

def run_retraining_loop(interval: int = 60):
    """
    Loop that runs indefinitely, checking for new feedback entries
    and retraining models when threshold is met.
    """
    log_to_file("✅ Retrain worker started and running (threshold = 5)")

    while True:
        try:
            # Get latest feedback and delta since last retrain
            current_count = get_feedback_count()
            last_count = load_last_retrain_count()
            new_entries = current_count - last_count

            log_to_file(f"🧠 Feedback total: {current_count} | New since last: {new_entries}")

            if new_entries >= FEEDBACK_THRESHOLD:
                log_to_file("⚙️  Threshold met — starting retraining...")
                log_to_file("🔁 [START] Model retraining initiated...")

                # Perform full retraining and return performance metrics
                report = train_all_models()

                # Log the training report (model metrics)
                log_to_file("📊 [REPORT] Model metrics:\n" + json.dumps(report, indent=2))
                write_training_log("📊 Model training summary:\n" + json.dumps(report, indent=2), source="retrain_worker")

                # Update the state to reflect retrain completion
                save_retrain_state(current_count)
                log_to_file("✅ Retraining complete and state saved")

            else:
                log_to_file(f"⏭️  Skipping — need {FEEDBACK_THRESHOLD}, only {new_entries} new")

        except Exception as e:
            log_to_file(f"❌ Uncaught error: {str(e)}")

        log_to_file(f"⏳ Sleeping for {interval} seconds...\n")
        time.sleep(interval)

# === Entrypoint ===

if __name__ == "__main__":
    run_retraining_loop()
