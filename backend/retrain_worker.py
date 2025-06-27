# backend/retrain_worker.py
# ✅ Auto-retrains all models every hour — runs forever on Render background worker

import time
from datetime import datetime
from train_all_models import train_all_models

def run_retraining_loop(interval=3600):
    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n🧠 [{timestamp}] Starting scheduled retraining cycle...")
            train_all_models()
            print(f"✅ [{timestamp}] Retraining completed successfully.\n")
        except Exception as e:
            print(f"❌ Error during retraining at {timestamp}: {e}")

        print(f"⏳ Waiting {interval} seconds until next retraining...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_retraining_loop()
