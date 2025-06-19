import pandas as pd
from train_model import train_model_from_feedback

def train_from_feedback(csv_path="backend/feedback.csv"):
    """
    Loads labeled feedback data from CSV and retrains the model.
    """
    print(f"📂 Reading feedback data from: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ File not found: {csv_path}")
        return
    except Exception as e:
        print(f"❌ Failed to load CSV: {e}")
        return

    if "belief" not in df.columns or "strategy_label" not in df.columns:
        print("❌ CSV missing required columns: 'belief' and 'strategy_label'")
        return

    print(f"📊 Loaded {len(df)} feedback records. Starting training...")
    train_model_from_feedback(df)
    print("✅ Feedback model updated successfully.")
