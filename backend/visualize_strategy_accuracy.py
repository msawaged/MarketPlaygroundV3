# backend/visualize_strategy_accuracy.py

"""
Visualizes the accuracy of the trained strategy model using a confusion matrix
and classification report. Helps analyze per-strategy prediction quality.
"""

import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, classification_report
from sklearn.model_selection import train_test_split

# === Import shared feature combiner (prevents pickle error) ===
from backend.utils.feature_utils import combine_features

# === Step 1: Load cleaned training data ===
try:
    df = pd.read_csv("backend/training_data/cleaned_strategies.csv")  # ✅ Matches training
except FileNotFoundError:
    raise RuntimeError("❌ File not found: backend/training_data/cleaned_strategies.csv")

# Remove any invalid rows
df.dropna(subset=['belief', 'strategy'], inplace=True)
df = df[df['belief'].str.strip() != '']
df = df[df['strategy'].str.strip() != '']

# === Step 2: Prepare features and labels ===
X_raw = df[['belief', 'ticker', 'direction', 'confidence', 'asset_class']]
y_raw = df['strategy']

# === Step 3: Load label encoder and encode labels ===
encoder = joblib.load("backend/strategy_label_encoder.joblib")
y_encoded = encoder.transform(y_raw)

# === Step 4: Train/test split (same seed as training) ===
X_train, X_test, y_train, y_test = train_test_split(
    X_raw, y_encoded, test_size=0.2, random_state=42
)

# === Step 5: Load trained model pipeline ===
pipeline = joblib.load("backend/smart_strategy_pipeline.joblib")

# === Step 6: Make predictions on test set ===
y_pred = pipeline.predict(X_test)

# === Step 7: Plot confusion matrix ===
labels = encoder.classes_
cm = confusion_matrix(y_test, y_pred)

plt.figure(figsize=(12, 8))
sns.heatmap(cm, annot=True, fmt='d', cmap="Blues", xticklabels=labels, yticklabels=labels)
plt.title("🧠 Confusion Matrix — Strategy Prediction")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)
plt.tight_layout()
plt.show()

# === Step 8: Print classification report ===
report = classification_report(y_test, y_pred, target_names=labels)
print("\n📊 Classification Report:\n")
print(report)
