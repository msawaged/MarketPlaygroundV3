"""
News Ingestor:
Fetches RSS headlines → creates belief → sends to backend →
logs strategy → triggers retraining.
"""

import feedparser
import requests
import datetime
import os
import csv
import random
import sys

from backend.utils.logger import write_training_log

# === Config ===
BACKEND_URL = "https://marketplayground-backend.onrender.com/strategy/process_belief"
RETRAIN_URL = "https://marketplayground-backend.onrender.com/force_retrain"
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"
TRAINING_PATH = "backend/Training_Strategies.csv"

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.zerohedge.com/fullrss.xml"
]

FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

def fetch_news_entries(limit_per_feed=5):
    """
    Parses all RSS feeds and returns clean (title, summary) entries.
    """
    entries = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and len(title) > 20:
                    entries.append((title, summary))
        except Exception as e:
            print(f"⚠️ Feed error from {url}: {e}", file=sys.stderr)
    return entries

def log_raw_belief(title, summary, belief):
    """
    Logs the raw belief generated from a news headline to CSV.
    """
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])

def log_training_row(belief, strategy, asset_class):
    """
    Logs belief-strategy-asset class combo to training data CSV.
    """
    with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([belief, strategy, asset_class])

def send_to_backend(belief_text):
    """
    Sends the belief to your FastAPI backend for strategy generation.
    Logs result for ML training.
    """
    try:
        payload = {"belief": belief_text, "user_id": "news_ingestor"}
        r = requests.post(BACKEND_URL, json=payload)

        if r.status_code == 200:
            response = r.json()
            strategy = response.get("strategy", {}).get("type", "unknown")
            asset_class = response.get("asset_class", "unknown")
            print(f"✅ Strategy generated: {belief_text[:60]}...", file=sys.stderr)
            log_training_row(belief_text, strategy, asset_class)
        else:
            print(f"❌ Backend error {r.status_code}: {belief_text[:60]}", file=sys.stderr)

    except Exception as e:
        print(f"❌ Request error: {e}", file=sys.stderr)

def trigger_retraining():
    """
    Manually triggers the backend model retraining endpoint.
    """
    try:
        r = requests.post(RETRAIN_URL)
        if r.status_code == 200:
            print("🔁 Retraining triggered", file=sys.stderr)
        else:
            print(f"❌ Retrain failed — Status: {r.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Retrain exception: {e}", file=sys.stderr)

def run_news_ingestor():
    """
    Main loop — fetch news, extract belief, send to backend, log, retrain.
    """
    print(f"\n🚀 News Ingestor started: {datetime.datetime.now()}", file=sys.stderr)
    entries = fetch_news_entries()
    print(f"📰 News fetched: {len(entries)}", file=sys.stderr)

    if not entries:
        fallback = random.choice(FALLBACK_BELIEFS)
        print("⚠️ No news — using fallback belief", file=sys.stderr)
        send_to_backend(fallback)
        write_training_log("📰 News fetched: 0\n🧠 Beliefs generated: 1\n➕ New beliefs added: 1")
    else:
        for title, summary in entries:
            belief = f"{title}. {summary[:150]}"
            send_to_backend(belief)
            log_raw_belief(title, summary, belief)
        write_training_log(
            f"📰 News fetched: {len(entries)}\n🧠 Beliefs generated: {len(entries)}\n➕ New beliefs added: {len(entries)}"
        )

    trigger_retraining()
    print(f"✅ News Ingestor completed at {datetime.datetime.now()}", file=sys.stderr)

# === Entrypoint ===
if __name__ == "__main__":
    run_news_ingestor()
