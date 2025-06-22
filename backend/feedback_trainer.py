import json
import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import os

# ✅ Define dynamic path to JSON and output model
base_dir = os.path.dirname(os.path.abspath(__file__))
feedback_file = os.path.join(base_dir, "feedback_data.json")
model_output = os.path.join(base_dir, "feedback_model.joblib")

# ✅ Load and normalize feedback data
with open(feedback_file, "r") as f:
    raw_data = json.load(f)

clean_data = []

for entry in raw_data:
    belief = entry.get("belief", "")
    feedback = entry.get("feedback") or entry.get("result")
    strategy = entry.get("strategy", {})

    # Normalize strategy into text
    if isinstance(strategy, dict):
        strategy_text = f"{strategy.get('type', '')} {strategy.get('description', '')} {strategy.get('risk_level', '')} {strategy.get('suggested_allocation', '')}"
    else:
        strategy_text = str(strategy)

    if belief and feedback and strategy_text:
        clean_data.append({
            "text": f"{belief} => {strategy_text}",
            "label": 1 if feedback.lower() == "good" else 0
        })

# ✅ Check data quality
if not clean_data:
    print("❌ No valid data found in feedback_data.json.")
    exit()

# ✅ Convert to DataFrame
df = pd.DataFrame(clean_data)
print("✅ Loaded training data:")
print(df.head())

# ✅ Train/test split
X_train, X_test, y_train, y_test = train_test_split(df["text"], df["label"], test_size=0.2, random_state=42)

# ✅ Build pipeline: TF-IDF + Logistic Regression
pipeline = Pipeline([
    ('tfidf', TfidfVectorizer()),
    ('clf', LogisticRegression())
])

pipeline.fit(X_train, y_train)
print("✅ Model trained.")

# ✅ Evaluate and show results
y_pred = pipeline.predict(X_test)
print("📊 Classification Report:")
print(classification_report(y_test, y_pred))

# ✅ Save the model
joblib.dump(pipeline, model_output)
print(f"✅ Feedback model saved to {model_output}")
