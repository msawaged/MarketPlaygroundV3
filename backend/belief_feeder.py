# backend/belief_feeder.py

"""
This background worker:
1. Pulls headlines + summaries from financial RSS feeds
2. Converts them into natural-language beliefs
3. Appends *only new* beliefs to clean_belief_tags.csv
4. Retrains all models with updated beliefs
"""

import time
import random
import csv
import os
import hashlib
from datetime import datetime
import feedparser

from backend.train_all_models import train_all_models

# === RSS sources to pull market news from ===
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]

# === Tag pool for fast random labeling ===
TAGS = ["bullish", "bearish", "neutral", "volatility", "rate_sensitive"]

# === Where to save beliefs for training ===
BELIEF_CSV_PATH = "backend/training_data/clean_belief_tags.csv"

# === Keywords that qualify a headline as finance-relevant ===
RELEVANT_KEYWORDS = [
    "stock", "stocks", "market", "markets", "fed", "interest", "inflation", "AI",
    "bond", "crypto", "bitcoin", "nasdaq", "dow", "s&p", "apple", "nvidia",
    "tesla", "google", "amazon", "earnings", "economy", "oil", "gold"
]

def fetch_headlines_with_summaries():
    """Fetches (title + summary) pairs from RSS feeds, filters by keywords."""
    combined = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title = entry.title.strip() if hasattr(entry, "title") else ""
                summary = entry.summary.strip() if hasattr(entry, "summary") else ""
                if not title or len(title) < 10:
                    continue
                full_text = f"{title}. {summary}".strip()

                # Filter only if any relevant keyword is in the full_text
                if any(k.lower() in full_text.lower() for k in RELEVANT_KEYWORDS):
                    combined.append(full_text)

        except Exception as e:
            print(f"⚠️ Failed to parse feed: {url}\n{e}")
            continue

    return combined

def convert_to_beliefs(lines):
    """Converts parsed lines into natural-language belief-style prompts."""
    templates = [
        "I believe {line}",
        "This matters: {line}",
        "The market might react to this: {line}",
        "Should I act on this? {line}",
        "Does this mean something big? {line}",
        "Based on this news: {line}"
    ]
    return [random.choice(templates).format(line=l) for l in lines]

def hash_belief(belief: str) -> str:
    """Returns an MD5 hash of a belief string."""
    return hashlib.md5(belief.encode("utf-8")).hexdigest()

def load_existing_belief_hashes(path=BELIEF_CSV_PATH):
    """Loads hashes of previously stored beliefs to avoid duplication."""
    if not os.path.exists(path):
        return set()
    with open(path, mode="r", newline='') as f:
        reader = csv.DictReader(f)
        return set(hash_belief(row["belief"]) for row in reader if "belief" in row)

def append_new_beliefs(beliefs, path=BELIEF_CSV_PATH):
    """Appends only *new* belief strings to CSV with a random tag."""
    existing_hashes = load_existing_belief_hashes(path)
    new_entries = [(b, hash_belief(b)) for b in beliefs if hash_belief(b) not in existing_hashes]

    if not new_entries:
        print(f"[{datetime.now()}] ⚠️ No new beliefs to add.")
        return 0

    file_exists = os.path.isfile(path)
    with open(path, mode="a", newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["belief", "tag"])
        for belief, _ in new_entries:
            tag = random.choice(TAGS)
            writer.writerow([belief, tag])
            print(f"➕ Saved belief: {belief[:80]}... [{tag}]")  # Optional debug log

    print(f"[{datetime.now()}] ✅ Added {len(new_entries)} new beliefs to clean_belief_tags.csv")
    return len(new_entries)

def run_feeder_loop(interval=3600):
    """Runs the full belief ingestion + retraining loop."""
    while True:
        print(f"\n📰 [News Feeder] Running at {datetime.now()}")

        try:
            raw_lines = fetch_headlines_with_summaries()
            print(f"🔍 Fetched {len(raw_lines)} relevant news items")

            beliefs = convert_to_beliefs(raw_lines)
            print(f"🧠 Generated {len(beliefs)} belief candidates")

            if not beliefs:
                print("⚠️ No beliefs generated, injecting dummy fallback for testing...")
                beliefs = ["I believe the market will move soon due to global volatility."]

            new_count = append_new_beliefs(beliefs)

            if new_count > 0:
                print("🔁 Retraining models with updated belief data...")
                train_all_models()
                print("✅ Retraining complete")
            else:
                print("⏩ Skipping retraining (no new data)")

        except Exception as e:
            print(f"❌ [Error] {e}")

        print(f"😴 Sleeping for {interval} seconds...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_feeder_loop()
