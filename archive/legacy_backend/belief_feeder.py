# backend/belief_feeder.py

"""
Background worker that:
1. Pulls financial headlines
2. Converts them to beliefs
3. Saves new beliefs to training_data
4. Triggers model retraining (if needed)
5. Logs status to backend/logs/last_training_log.txt
"""

import time
import random
import csv
import os
import hashlib
from datetime import datetime
import feedparser

from train_all_models import train_all_models

# === CONFIG ===
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]
TAGS = ["bullish", "bearish", "neutral", "volatility", "rate_sensitive"]
BELIEF_CSV_PATH = "backend/training_data/clean_belief_tags.csv"
LOG_PATH = "backend/logs/last_training_log.txt"
RELEVANT_KEYWORDS = [
    "stock", "stocks", "market", "markets", "fed", "interest", "inflation", "AI",
    "bond", "crypto", "bitcoin", "nasdaq", "dow", "s&p", "apple", "nvidia",
    "tesla", "google", "amazon", "earnings", "economy", "oil", "gold"
]

# === SETUP ON STARTUP ===
os.makedirs(os.path.dirname(BELIEF_CSV_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def fetch_headlines_with_summaries():
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
                if any(k.lower() in full_text.lower() for k in RELEVANT_KEYWORDS):
                    combined.append(full_text)
        except Exception as e:
            print(f"⚠️ Failed to parse feed: {url}\n{e}")
            continue
    return combined

def convert_to_beliefs(lines):
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
    return hashlib.md5(belief.encode("utf-8")).hexdigest()

def load_existing_belief_hashes(path=BELIEF_CSV_PATH):
    if not os.path.exists(path):
        return set()
    with open(path, mode="r", newline='') as f:
        reader = csv.DictReader(f)
        return set(hash_belief(row["belief"]) for row in reader if "belief" in row)

def append_new_beliefs(beliefs, path=BELIEF_CSV_PATH):
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
            print(f"➕ Saved: {belief[:80]}... [{tag}]")
    print(f"[{datetime.now()}] ✅ Added {len(new_entries)} new beliefs.")
    return len(new_entries)

def write_log(timestamp, fetched, generated, new_count, retrained):
    with open(LOG_PATH, "w") as f:
        f.write(f"🕒 {timestamp}\n")
        f.write(f"📰 News fetched: {fetched}\n")
        f.write(f"🧠 Beliefs generated: {generated}\n")
        f.write(f"➕ New beliefs added: {new_count}\n")
        f.write("✅ Models retrained.\n" if retrained else "⏩ Skipped retraining.\n")

def run_feeder_loop(interval=3600):
    while True:
        timestamp = datetime.now()
        print(f"\n📰 [News Ingestor] {timestamp}")

        try:
            raw_lines = fetch_headlines_with_summaries()
            print(f"🔍 {len(raw_lines)} headlines fetched")

            beliefs = convert_to_beliefs(raw_lines)
            print(f"🧠 {len(beliefs)} belief prompts generated")

            if not beliefs:
                print("⚠️ No beliefs found. Using fallback.")
                beliefs = ["I believe the market may react to rising uncertainty."]

            new_count = append_new_beliefs(beliefs)
            retrained = False

            if new_count > 0:
                try:
                    print("🔁 Starting retraining...")
                    train_all_models()
                    retrained = True
                    print("✅ Retraining complete")
                except Exception as e:
                    print(f"❌ Model training failed: {e}")

            write_log(timestamp, len(raw_lines), len(beliefs), new_count, retrained)

        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            write_log(timestamp, 0, 0, 0, False)

        print(f"😴 Sleeping {interval} seconds...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_feeder_loop()
