# train_belief_classifier.py
# Trains a basic ML model to classify user beliefs into trading tags

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib

# Training data: beliefs and manually labeled tags
beliefs = [
    ("TSLA will explode next week", "bullish-short-high"),
    ("I think AAPL is overvalued", "bearish-long-medium"),
    ("market will be flat tomorrow", "neutral-short-low"),
    ("investing long term in AI", "bullish-long-medium"),
    ("volatility is coming", "neutral-short-high"),
    ("the economy is in trouble", "bearish-long-high"),
    ("this week is uncertain", "neutral-short-medium"),
    ("I want to hold a clean energy ETF for years", "bullish-long-low"),
    ("NVDA looks risky short term", "bearish-short-high")
]

texts, labels = zip(*beliefs)

# Convert text to vector format
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(texts)

# Train classifier
clf = MultinomialNB()
clf.fit(X, labels)

# Save model + vectorizer
joblib.dump(clf, "belief_model.joblib")
joblib.dump(vectorizer, "belief_vectorizer.joblib")

print("✅ Belief classifier trained and saved.")
