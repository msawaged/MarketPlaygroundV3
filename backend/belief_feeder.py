# backend/belief_feeder.py

"""
This background worker:
1. Pulls headlines from RSS feeds
2. Converts them into natural-language beliefs
3. Appends *only new* beliefs to clean_belief_tags.csv
4. Retrains all models with updated beliefs
"""

import time
import random
import csv
import os
from datetime import datetime
import feedparser

from backend.train_all_models import train_all_models

# RSS sources to pull market news from
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]

# Temporary tag labels used for fast labeling
TAGS = ["bullish", "bearish", "neutral", "volatility", "rate_sensitive"]

# Filepath where beliefs are stored and used for retraining
BELIEF_CSV_PATH = "backend/training_data/clean_belief_tags.csv"

def fetch_headlines():
    """Fetches the latest headlines from RSS feeds."""
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            title = entry.title.strip()
            if title and len(title) > 20:
                headlines.append(title)
    return headlines

def convert_to_beliefs(headlines):
    """Converts headlines into belief-style statements."""
    templates = [
        "I believe {headline}",
        "Based on this news: {headline}",
        "Should I act on this? {headline}",
    ]
    return [random.choice(templates).format(headline=h) for h in headlines]

def load_existing_beliefs(path=BELIEF_CSV_PATH):
    """Loads all existing beliefs from CSV to prevent duplicates."""
    if not os.path.exists(path):
        return set()
    with open(path, mode="r", newline='') as f:
        reader = csv.DictReader(f)
        return set(row["belief"] for row in reader if "belief" in row)

def append_new_beliefs(beliefs, path=BELIEF_CSV_PATH):
    """Appends only *new* beliefs to the CSV with random tag labels."""
    existing = load_existing_beliefs(path)
    new_entries = [b for b in beliefs if b not in existing]

    if not new_entries:
        print("⚠️ No new beliefs to add.")
        return

    file_exists = os.path.isfile(path)
    with open(path, mode="a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["belief", "tag"])
        for belief in new_entries:
            tag = random.choice(TAGS)
            writer.writerow([belief, tag])
    
    print(f"✅ Added {len(new_entries)} new beliefs to clean_belief_tags.csv")

def run_feeder_loop(interval=3600):
    """Runs the full news→belief→training loop repeatedly."""
    while True:
        print(f"\n📰 [News Feeder] Running at {datetime.now()}")

        # Fetch → Convert → Dedup → Append
        headlines = fetch_headlines()
        beliefs = convert_to_beliefs(headlines)
        append_new_beliefs(beliefs)

        # Retrain on updated data
        print("🔁 Retraining models with fresh belief data...")
        train_all_models()
        print(f"✅ Cycle complete. Sleeping {interval} seconds...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_feeder_loop()
