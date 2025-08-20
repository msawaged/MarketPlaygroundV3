# backend/retrain_worker.py
# ✅ Background worker to auto-retrain all models when enough new feedback or news beliefs are logged

import time
import os
import json
import pandas as pd
from datetime import datetime

from train_all_models import train_all_models
from backend.utils.logger import write_training_log

# === Directory setup ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOG_DIR, "retrain_worker.log")
STATE_PATH = os.path.join(LOG_DIR, "last_retrain.json")

FEEDBACK_PATH = os.path.join(BASE_DIR, "feedback.csv")
NEWS_PATH = os.path.join(BASE_DIR, "news_beliefs.csv")

# === Threshold config ===
FEEDBACK_THRESHOLD = 0
NEWS_THRESHOLD = 0

# === Logging ===
def log_to_file(message: str):
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    full = f"[{timestamp}] {message}"
    try:
        with open(LOG_PATH, "a") as f:
            f.write(full + "\n")
    except Exception as e:
        print(f"❌ File logging failed: {str(e)}")
    print(full)
    write_training_log(message, source="retrain_worker")

# === Load row counts ===
def get_row_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        return len(pd.read_csv(path))
    except Exception as e:
        log_to_file(f"❌ Failed to read {path}: {str(e)}")
        return 0

# === Save retrain state ===
def save_state(feedback_count: int, news_count: int):
    with open(STATE_PATH, "w") as f:
        json.dump({
            "feedback_count": feedback_count,
            "news_count": news_count,
            "timestamp": datetime.utcnow().isoformat()
        }, f)

# === Load retrain state ===
def load_state() -> tuple:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as f:
                data = json.load(f)
                return (
                    data.get("feedback_count", 0),
                    data.get("news_count", 0)
                )
        except Exception:
            return (0, 0)
    return (0, 0)

# === Main loop ===
def run_retraining_loop(interval: int = 60):
    log_to_file("✅ Retrain worker started (dual trigger: feedback + news)")

    while True:
        try:
            current_feedback = get_row_count(FEEDBACK_PATH)
            current_news = get_row_count(NEWS_PATH)
            last_feedback, last_news = load_state()

            delta_feedback = current_feedback - last_feedback
            delta_news = current_news - last_news

            log_to_file(f"🧠 Feedback: {current_feedback} (Δ {delta_feedback}) | News: {current_news} (Δ {delta_news})")

            if delta_feedback >= FEEDBACK_THRESHOLD or delta_news >= NEWS_THRESHOLD:
                trigger_source = []
                if delta_feedback >= FEEDBACK_THRESHOLD:
                    trigger_source.append("feedback")
                if delta_news >= NEWS_THRESHOLD:
                    trigger_source.append("news")

                log_to_file(f"⚙️  Threshold met via {', '.join(trigger_source)} — starting retraining...")
                log_to_file("🔁 [START] Model retraining initiated...")

                report = train_all_models()

                log_to_file("📊 [REPORT] Model metrics:\n" + json.dumps(report, indent=2))
                write_training_log("📊 Model training summary:\n" + json.dumps(report, indent=2), source="retrain_worker")

                save_state(current_feedback, current_news)
                log_to_file("✅ Retraining complete and state saved")
            else:
                log_to_file(f"⏭️  Skipping — thresholds not met")

        except Exception as e:
            log_to_file(f"❌ Uncaught error: {str(e)}")

        log_to_file(f"⏳ Sleeping for {interval} seconds...\n")
        time.sleep(interval)

# === Entrypoint ===
if __name__ == "__main__":
    run_retraining_loop()
