# backend/utils/training_trigger.py
# ✅ Triggers retraining by hitting the backend /retrain endpoint

import requests

RETRAIN_URL = "https://marketplayground-backend.onrender.com/retrain"

def trigger_retraining():
    """
    Sends a POST request to the backend to trigger model retraining.
    """
    try:
        response = requests.post(RETRAIN_URL)
        if response.status_code == 200:
            print("🚀 Retraining triggered successfully")
        else:
            print(f"⚠️ Failed to trigger retraining — Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error triggering retraining: {e}")
