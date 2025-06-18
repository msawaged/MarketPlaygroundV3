# backend/retrain_worker.py

import time
import traceback
from backend.train_from_feedback import main as retrain_model

def loop_forever(interval=3600):
    print("[retrain_worker] 🔁 Starting background retrain loop...")
    while True:
        try:
            retrain_model()
            print("[retrain_worker] ✅ Model retrained successfully.")
        except Exception as e:
            print(f"[retrain_worker] ❌ Error during retraining: {e}")
            traceback.print_exc()
        time.sleep(interval)

if __name__ == "__main__":
    loop_forever()
