# retrain_worker.py
# Background worker to retrain models periodically

import time
from train_all_models import train_all_models

def run_retraining_loop(interval=3600):
    while True:
        print("🔄 Running scheduled retraining...")
        train_all_models()
        print("⏲️ Waiting for next retraining cycle...")
        time.sleep(interval)

if __name__ == "__main__":
    run_retraining_loop(interval=3600)  # Retrain every hour
