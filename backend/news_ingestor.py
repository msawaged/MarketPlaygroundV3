# backend/news_ingestor.py

"""
News Ingestor: Fetches RSS news → generates belief → POSTs to backend → logs for training
"""

import feedparser
import random
import requests
import time
import datetime
import os
import csv

BACKEND_URL = "http://127.0.0.1:8000/process_belief"  # Use localhost for testing
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"
TRAINING_PATH = "backend/Training_Strategies.csv"

RSS_FEEDS = [
    "https://www.marketwatch.com/rss/topstories",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.zerohedge.com/fullrss.xml"
]

TEMPLATES = [
    "I believe {headline}. Summary: {summary}",
    "News just broke: {headline} — {summary}",
    "What might happen after this? {headline}. Details: {summary}",
    "Should I trade based on this? {headline}. Context: {summary}"
]

FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

def generate_belief_prompt(title, summary=""):
    return random.choice(TEMPLATES).format(
        headline=title.strip(),
        summary=summary.strip()[:200] or "No summary provided"
    )

def fetch_news_entries(limit_per_feed=5):
    entries = []
    for url in RSS_FEEDS:
        try:
            print(f"🔗 Fetching from: {url}")
            feed = feedparser.parse(url)
            print(f"✅ Parsed {len(feed.entries)} entries from {url}")
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and len(title) > 20:
                    entries.append((title, summary))
        except Exception as e:
            print(f"⚠️ Feed error: {url} → {e}")
    return entries

def log_raw_belief(title, summary, belief):
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    try:
        with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])
    except Exception as e:
        print(f"❌ Logging raw belief error: {e}")

def log_training_row(belief, strategy, asset_class):
    try:
        with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([belief, strategy, asset_class])
    except Exception as e:
        print(f"❌ Training log error: {e}")

def send_belief_to_backend(belief, title="", summary=""):
    try:
        r = requests.post(BACKEND_URL, json={"belief": belief})
        if r.status_code == 200:
            response = r.json()
            strategy = response.get("strategy", "unknown")
            asset_class = response.get("asset_class", "unknown")
            print(f"✅ [{strategy}] {belief[:60]}...")
            log_training_row(belief, strategy, asset_class)
        else:
            print(f"❌ Backend error ({r.status_code}): {belief[:60]}")
        log_raw_belief(title, summary, belief)
    except Exception as e:
        print(f"❌ Request error: {e}")

def run_news_ingestor(interval=300):
    while True:
        print(f"\n📰 [{datetime.datetime.now()}] News Ingestor Running")
        entries = fetch_news_entries()
        print(f"🔍 Found {len(entries)} headlines")

        if not entries:
            fallback = random.choice(FALLBACK_BELIEFS)
            print("⚠️ No headlines, using fallback")
            send_belief_to_backend(fallback, "Fallback", "")
        else:
            for title, summary in entries:
                belief = generate_belief_prompt(title, summary)
                send_belief_to_backend(belief, title, summary)

        print(f"⏲️ Sleeping {interval} sec...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_news_ingestor()
