# backend/belief_feeder.py

import time
import random
import csv
import os
from datetime import datetime
from backend.train_all_models import train_all_models
import feedparser

RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]

TAGS = ["bullish", "bearish", "neutral", "volatility", "rate_sensitive"]

def fetch_headlines():
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            title = entry.title.strip()
            if title and len(title) > 20:
                headlines.append(title)
    return headlines

def convert_to_beliefs(headlines):
    templates = [
        "I believe {headline}",
        "Based on this news: {headline}",
        "Should I act on this? {headline}",
    ]
    return [random.choice(templates).format(headline=h) for h in headlines]

def append_to_csv(beliefs, path="backend/training_data/clean_belief_tags.csv"):
    file_exists = os.path.isfile(path)
    with open(path, mode="a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["belief", "tag"])
        for belief in beliefs:
            tag = random.choice(TAGS)
            writer.writerow([belief, tag])
    print(f"✅ Added {len(beliefs)} new beliefs to clean_belief_tags.csv")

def run_feeder_loop(interval=3600):
    while True:
        print(f"\n📰 Generating fresh beliefs at {datetime.now()}")
        headlines = fetch_headlines()
        beliefs = convert_to_beliefs(headlines)
        append_to_csv(beliefs)
        print("🔁 Retraining with updated beliefs...")
        train_all_models()
        print("⏲️ Waiting for next cycle...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_feeder_loop()
