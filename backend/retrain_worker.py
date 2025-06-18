# backend/retrain_worker.py

import time
import traceback
from train_from_feedback import main as retrain_feedback
from train_model import train_main_model
from train_multi_asset_model import train_multi_asset_model
from utils import log

RETRAIN_INTERVAL_SECONDS = 1800  # 30 minutes

def background_retrain_loop():
    while True:
        try:
            log("🔁 Retraining all models from feedback data...")
            retrain_feedback()  # Feedback-based sentiment model
            train_main_model()  # Belief direction / asset class
            train_multi_asset_model()  # Multi-asset strategy model
            log("✅ All models retrained and saved.")
        except Exception as e:
            log(f"❌ Retrain loop failed: {e}")
            traceback.print_exc()
        time.sleep(RETRAIN_INTERVAL_SECONDS)

if __name__ == "__main__":
    background_retrain_loop()
