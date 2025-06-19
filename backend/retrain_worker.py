# backend/retrain_worker.py

"""
✅ FINAL: Auto-retrainer for all models on Render
Fixes ModuleNotFoundError by using absolute import path from backend package.
"""

import os
import sys

# Add backend directory to system path for reliable imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Safe import from same folder
from train_all_models import train_all_models

print("🔁 Starting full backend model retraining...")

try:
    train_all_models()
    print("✅ All models retrained successfully.")
except Exception as e:
    print(f"❌ Error during model retraining: {e}")
