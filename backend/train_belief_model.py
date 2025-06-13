# train_belief_model.py
# Trains a multi-output model to classify user beliefs into direction, duration, and volatility

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multioutput import MultiOutputClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

print("\n📊 Loading belief data...")
df = pd.read_csv("belief_data.csv")

# ✅ Drop any rows with missing values
df = df.dropna()

# 📌 Features and Labels
X = df["belief_text"]  # Natural-language user belief
y = df[["direction", "duration", "volatility"]]  # Multi-label output

# 🔢 Convert text beliefs to numerical vectors
vectorizer = TfidfVectorizer()
X_vec = vectorizer.fit_transform(X)

# ✂️ Train/Test Split
X_train, X_test, y_train, y_test = train_test_split(X_vec, y, test_size=0.2, random_state=42)

# 🧠 Multi-label model (RandomForest wrapped in MultiOutputClassifier)
model = MultiOutputClassifier(RandomForestClassifier(n_estimators=100, random_state=42))
model.fit(X_train, y_train)

# 🔍 Evaluate performance per label
y_pred = model.predict(X_test)
y_pred_df = pd.DataFrame(y_pred, columns=y.columns)

print("\n📊 Classification Report (per label):\n")
for label in y.columns:
    print(f"🔹 {label.upper()}:")
    print(classification_report(y_test[label], y_pred_df[label]))
    print("----------------------------------------")

# 💾 Save the model + vectorizer
joblib.dump(model, "belief_model.joblib")
joblib.dump(vectorizer, "belief_vectorizer.joblib")
print("\n✅ belief_model.joblib and belief_vectorizer.joblib saved.")
