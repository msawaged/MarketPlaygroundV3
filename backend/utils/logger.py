# backend/utils/logger.py
# ✅ Central utility for logging training activity to Render and local logs

import os
from datetime import datetime

def write_training_log(message: str):
    """
    Writes a timestamped message to both:
    1. backend/logs/last_training_log.txt — latest summary for ingestion tracking
    2. backend/logs/retrain_worker.log — persistent log for retraining
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"\n🕒 {timestamp}\n{message}\n"

    log_dir = os.path.join("backend", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # ✅ 1. Overwrite the last training summary
    last_log_path = os.path.join(log_dir, "last_training_log.txt")
    with open(last_log_path, "w") as f:
        f.write(full_message)

    # ✅ 2. Append to persistent retrain log
    retrain_log_path = os.path.join(log_dir, "retrain_worker.log")
    with open(retrain_log_path, "a") as f:
        f.write(full_message)

    # ✅ Also print to console/logs
    print(full_message.strip())
