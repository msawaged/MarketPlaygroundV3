# retrain_worker.py
# This background worker is triggered by Render to retrain your ML models
# using the feedback data collected in feedback.csv.

# ✅ Correct import: since this file is inside backend/, import directly
from train_from_feedback import main as retrain_model

if __name__ == "__main__":
    print("🔁 Starting model retraining from feedback.csv...")
    
    # Call the retraining function
    retrain_model()
    
    print("✅ Retraining complete.")
