# backend/retrain_worker.py
# ✅ Background worker: Automatically retrains all models on a schedule (every hour by default)

import time
from datetime import datetime

# ✅ Import the main training pipeline that handles all model retraining
from backend.train_all_models import train_all_models


def run_retraining_loop(interval: int = 3600):
    """
    Runs an infinite loop to retrain all models at the specified time interval (default: 3600s = 1 hour).
    Logs the time of each cycle and handles errors gracefully.
    
    Args:
        interval (int): Time in seconds between retraining cycles. Default is 3600 (1 hour).
    """
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            print(f"\n🧠 [{timestamp}] Starting scheduled retraining cycle...")

            # Call the full pipeline that retrains all ML models
            train_all_models()

            print(f"✅ [{timestamp}] Retraining completed successfully.\n")

        except Exception as e:
            print(f"❌ [{timestamp}] Error during retraining: {str(e)}\n")

        # Sleep until the next scheduled cycle
        print(f"⏳ Sleeping for {interval} seconds until next retraining cycle...\n")
        time.sleep(interval)


if __name__ == "__main__":
    run_retraining_loop()
