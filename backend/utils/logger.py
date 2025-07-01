# backend/utils/logger.py
# ✅ Central utility for logging training activity to Render and local logs

import os
from datetime import datetime

def write_training_log(message: str):
    """
    Writes a timestamped message to backend/logs/last_training_log.txt.
    Auto-creates the logs directory if missing.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"\n🕒 {timestamp}\n{message}\n"

    log_dir = os.path.join("backend", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_path = os.path.join(log_dir, "last_training_log.txt")
    with open(log_path, "w") as f:
        f.write(full_message)

    print(full_message.strip())  # Print for console visibility as well
