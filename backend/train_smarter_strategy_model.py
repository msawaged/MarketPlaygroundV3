# backend/train_smarter_strategy_model.py

"""
Trains a smarter ML pipeline for strategy generation using XGBoost.
Saves both the pipeline and label encoder for later inference and decoding.
"""

import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score

# ✅ Import reusable combine_features logic
from backend.utils.feature_utils import combine_features

def train_strategy_model():
    """
    Trains and saves a smart ML pipeline and label encoder.
    Returns:
        pipeline (Pipeline): trained pipeline
        encoder (LabelEncoder): label encoder for decoding predictions
        accuracy (float): test accuracy
    """
    # === Step 1: Load and clean training data ===
    DATA_PATH = os.path.join("backend", "training_data", "cleaned_strategies.csv")
    if not os.path.exists(DATA_PATH):
        raise RuntimeError(f"❌ File not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    df.dropna(subset=['belief', 'strategy'], inplace=True)
    df = df[df['belief'].str.strip() != '']
    df = df[df['strategy'].str.strip() != '']

    # === Step 2: Extract features and target labels ===
    X_raw = df[['belief', 'ticker', 'direction', 'confidence', 'asset_class']]
    y_raw = df['strategy']

    # === Step 3: Encode strategy labels ===
    encoder = LabelEncoder()
    y_encoded = encoder.fit_transform(y_raw)

    ENCODER_PATH = os.path.join("backend", "strategy_label_encoder.joblib")
    joblib.dump(encoder, ENCODER_PATH)

    # === Step 4: Define ML pipeline using imported combine_features ===
    pipeline = Pipeline([
        ("feature_combiner", FunctionTransformer(combine_features, validate=False)),
        ("vectorizer", TfidfVectorizer(ngram_range=(1, 2))),
        ("classifier", XGBClassifier(
            use_label_encoder=False,
            eval_metric="mlogloss",
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1
        ))
    ])

    # === Step 5: Train/test split ===
    X_train, X_test, y_train, y_test = train_test_split(
        X_raw, y_encoded, test_size=0.2, random_state=42
    )

    # === Step 6: Train the model ===
    pipeline.fit(X_train, y_train)

    # === Step 7: Save pipeline and encoder ===
    MODEL_PATH = os.path.join("backend", "smart_strategy_pipeline.joblib")
    joblib.dump(pipeline, MODEL_PATH)

    # === Step 8: Evaluate test accuracy ===
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    return pipeline, encoder, accuracy

# ✅ CLI test block
if __name__ == "__main__":
    print("🚀 Training smarter strategy model...")

    pipeline, encoder, accuracy = train_strategy_model()

    print(f"✅ Trained pipeline saved to backend/smart_strategy_pipeline.joblib")
    print(f"✅ Label encoder saved to backend/strategy_label_encoder.joblib")
    print(f"🎯 Accuracy on test set: {accuracy:.2f}")

    # === 🔬 Test case ===
    X_example = pd.DataFrame([{
        'belief': 'I think TSLA will surge after earnings',
        'ticker': 'TSLA',
        'direction': 'bullish',
        'confidence': 0.75,
        'asset_class': 'stock'
    }])

    y_example_pred = pipeline.predict(X_example)[0]
    strategy_label = encoder.inverse_transform([y_example_pred])[0]

    print(f"\n🔬 Test Belief: {X_example.iloc[0]['belief']}")
    print(f"🔮 Predicted Strategy: {strategy_label}")
