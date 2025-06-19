import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
import joblib
import os

def train_model_from_feedback(feedback_csv_path: str = "backend/feedback.csv"):
    """
    Reads user feedback from a CSV file and retrains the strategy classification model.
    Expects the CSV to have two columns: 'belief' and 'strategy_label'.

    Parameters:
    - feedback_csv_path (str): Path to the CSV file with feedback data.
    """

    print("🔁 Starting model retraining from feedback.csv...")

    # Ensure we are using absolute path in Render (or fallback for local)
    csv_path = os.path.abspath(feedback_csv_path)
    print(f"📂 Reading feedback data from: {csv_path}")

    try:
        # Read CSV into DataFrame
        df = pd.read_csv(csv_path)

        # ✅ Validate required columns
        expected_columns = ['belief', 'strategy_label']
        if not all(col in df.columns for col in expected_columns):
            print(f"❌ CSV missing required columns: {expected_columns}")
            return

        print(f"📊 Loaded {len(df)} feedback records. Starting training...")
        print(f"[train_model_from_feedback] 📂 Reading feedback data from: {df[['belief', 'strategy_label']]}")

        # Split data into features and labels
        X = df['belief']
        y = df['strategy_label']

        # Build a text classification pipeline
        model = make_pipeline(TfidfVectorizer(), LogisticRegression(max_iter=1000))

        # Train model on feedback
        model.fit(X, y)

        # Save the updated model and vectorizer
        joblib.dump(model, "backend/feedback_model.joblib")
        print("✅ Feedback model updated successfully.")

    except FileNotFoundError:
        print("❌ feedback.csv file not found.")
    except Exception as e:
        print(f"[train_model_from_feedback] ❌ Unexpected error: {e}")

    print("✅ Retraining complete.")
