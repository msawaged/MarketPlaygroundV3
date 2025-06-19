# retrain_worker.py
# 🔁 Background worker to retrain model using new feedback data

import os
from feedback_trainer import train_from_feedback  # ✅ Renamed import (was: train_from_feedback.py)

if __name__ == "__main__":
    print("🔁 Starting model retraining from feedback.csv...")

    # ✅ Resolve full path to feedback.csv for compatibility with both local and Render environments
    current_dir = os.path.dirname(os.path.abspath(__file__))
    feedback_path = os.path.join(current_dir, "feedback.csv")
    print(f"📂 Reading feedback data from: {feedback_path}")

    # ✅ Call training function with full path
    train_from_feedback(feedback_path)

    print("✅ Retraining complete.")
