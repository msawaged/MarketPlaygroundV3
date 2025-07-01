"""
News Ingestor: Fetches RSS news → generates belief → POSTs to backend → logs for training.
Also triggers model retraining after ingestion completes.
"""

import feedparser
import random
import requests
import time
import datetime
import os
import csv
import sys

from backend.utils.logger import write_training_log  # ✅ Logs summary to backend/logs/last_training_log.txt
from backend.utils.training_trigger import trigger_retraining  # ✅ Triggers model retraining after ingestion

# === Configuration ===
BACKEND_URL = "https://marketplayground-backend.onrender.com/process_belief"
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"         # Logs raw title → summary → belief
TRAINING_PATH = "backend/Training_Strategies.csv"       # Adds belief-strategy pairs for model training

# === RSS Feed Sources ===
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.zerohedge.com/fullrss.xml"
]

# === Templates to Turn Headlines into Beliefs ===
TEMPLATES = [
    "I believe {headline}. Summary: {summary}",
    "News just broke: {headline} — {summary}",
    "What might happen after this? {headline}. Details: {summary}",
    "Should I trade based on this? {headline}. Context: {summary}"
]

# === Fallback Beliefs ===
FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

def generate_belief_prompt(title, summary=""):
    """
    Creates a synthetic belief from a news title and summary.
    """
    return random.choice(TEMPLATES).format(
        headline=title.strip(),
        summary=summary.strip()[:200] or "No summary provided"
    )

def fetch_news_entries(limit_per_feed=5):
    """
    Pulls the latest headlines + summaries from all RSS feeds.
    """
    entries = []
    print(f"🔧 Total feeds: {len(RSS_FEEDS)}", file=sys.stderr)
    for url in RSS_FEEDS:
        try:
            print(f"🔗 Fetching from: {url}", file=sys.stderr)
            feed = feedparser.parse(url)
            if not feed.entries:
                raise ValueError("No entries returned")
            print(f"✅ Parsed {len(feed.entries)} entries from {url}", file=sys.stderr)
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and len(title) > 20:
                    entries.append((title, summary))
        except Exception as e:
            print(f"⚠️ Feed error: {url} → {e}", file=sys.stderr)
    return entries

def log_raw_belief(title, summary, belief):
    """
    Logs the raw title → summary → belief into news_beliefs.csv for review.
    """
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    try:
        with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])
    except Exception as e:
        print(f"❌ Logging raw belief error: {e}", file=sys.stderr)

def log_training_row(belief, strategy, asset_class):
    """
    Saves belief-strategy-asset_class row into Training_Strategies.csv for training.
    """
    try:
        with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([belief, strategy, asset_class])
    except Exception as e:
        print(f"❌ Training log error: {e}", file=sys.stderr)

def send_belief_to_backend(belief, title="", summary=""):
    """
    Sends a single belief to the /process_belief endpoint.
    Logs the strategy and asset class to the training dataset.
    """
    try:
        r = requests.post(BACKEND_URL, json={"belief": belief})
        if r.status_code == 200:
            response = r.json()
            strategy = response.get("strategy", {}).get("type", "unknown")
            asset_class = response.get("asset_class", "unknown")
            print(f"✅ [{strategy}] {belief[:60]}...", file=sys.stderr)
            log_training_row(belief, strategy, asset_class)
        else:
            print(f"❌ Backend error ({r.status_code}): {belief[:60]}", file=sys.stderr)
        log_raw_belief(title, summary, belief)
    except Exception as e:
        print(f"❌ Request error: {e}", file=sys.stderr)

def run_news_ingestor(interval=300):
    """
    Main loop: fetch news → create beliefs → send to backend → log → trigger retraining.
    """
    while True:
        print(f"\n🟢 News Ingestor started: {datetime.datetime.now()}", file=sys.stderr)
        entries = fetch_news_entries()
        print(f"🔍 Found {len(entries)} headlines", file=sys.stderr)

        # ✅ Write ingestion summary to logs
        write_training_log(
            f"📰 News fetched: {len(entries)}\n🧠 Beliefs generated: {len(entries) or 1}\n➕ New beliefs added: {len(entries) or 1}"
        )

        if not entries:
            fallback = random.choice(FALLBACK_BELIEFS)
            print("⚠️ No headlines found — using fallback", file=sys.stderr)
            send_belief_to_backend(fallback, "Fallback", "")
        else:
            print(f"✅ Proceeding with {len(entries)} headlines", file=sys.stderr)
            for title, summary in entries:
                belief = generate_belief_prompt(title, summary)
                send_belief_to_backend(belief, title, summary)

        # ✅ Trigger background retraining
        print("🚀 Triggering retraining after ingestion...", file=sys.stderr)
        try:
            trigger_retraining()
        except Exception as e:
            print(f"❌ Failed to trigger retraining: {e}", file=sys.stderr)

        print(f"🛑 Sleeping for {interval}s", file=sys.stderr)
        time.sleep(interval)

# === Entrypoint for Render Worker ===
if __name__ == "__main__":
    run_news_ingestor()
