# backend/utils/logger.py
# ✅ Central utility for logging training activity (Render + local safe)

import os
from datetime import datetime

# === Absolute log path that works from any entry point ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))        # backend/utils
LOG_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "logs"))  # backend/logs
os.makedirs(LOG_DIR, exist_ok=True)

def write_training_log(message: str):
    """
    Writes a timestamped message to both:
    1. backend/logs/last_training_log.txt — latest summary for ingestion tracking
    2. backend/logs/retrain_worker.log — persistent log for retraining
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"\n🕒 {timestamp}\n{message}\n"

    # ✅ 1. Overwrite the last training summary
    last_log_path = os.path.join(LOG_DIR, "last_training_log.txt")
    with open(last_log_path, "w") as f:
        f.write(full_message)

    # ✅ 2. Append to persistent retrain log
    retrain_log_path = os.path.join(LOG_DIR, "retrain_worker.log")
    with open(retrain_log_path, "a") as f:
        f.write(full_message)

    # ✅ Also print to console/logs
    print(full_message.strip())
