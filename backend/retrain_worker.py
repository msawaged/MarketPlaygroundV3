import os
import pandas as pd
from train_from_feedback import train_from_feedback

if __name__ == "__main__":
    print("🔁 Starting model retraining from feedback.csv...")

    # ✅ Dynamically determine the full path to feedback.csv
    # This ensures compatibility with local runs AND Render, regardless of root directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(backend_dir, "feedback.csv")

    try:
        # 🔁 Attempt to run the training pipeline using the feedback CSV
        train_from_feedback(csv_path)
        print("✅ Retraining complete.")
    except FileNotFoundError as fnf_error:
        print(f"[train_from_feedback] ❌ File not found: {csv_path}")
    except Exception as e:
        print(f"[train_from_feedback] ❌ Unexpected error: {e}")
