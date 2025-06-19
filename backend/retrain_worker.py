# backend/retrain_worker.py

"""
✅ FINAL: Render-compatible retraining script
This automatically retrains all models using the train_all_models() pipeline.
"""

import os
import sys

# Ensure the backend directory is in the path (important for cloud)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Now we can import from local file
from train_all_models import train_all_models

print("🔁 Starting full backend model retraining...")

try:
    train_all_models()
    print("✅ All models retrained successfully.")
except Exception as e:
    print(f"❌ Error during model retraining: {e}")
