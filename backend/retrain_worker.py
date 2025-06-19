# backend/retrain_worker.py

"""
This worker runs on Render to automatically retrain all models using feedback.csv
and regenerate belief, asset, strategy, and feedback models.
"""

import os
from train_all_models import train_all_models

# Dynamic path resolution for cloud compatibility
backend_dir = os.path.dirname(os.path.abspath(__file__))

print("🔁 Starting full backend model retraining...")

try:
    train_all_models()
    print("✅ All models retrained successfully.")
except Exception as e:
    print(f"❌ Error during model retraining: {e}")
