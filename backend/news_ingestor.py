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

# === Config ===
# IMPORTANT: Switch this to your Render URL when deploying
BACKEND_URL = "https://marketplayground-backend.onrender.com/process_belief"
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"
TRAINING_PATH = "backend/Training_Strategies.csv"

# === RSS Feed Sources (more reliable feeds added)
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",                    # ✅ Reliable
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",        # ✅ CNBC US Top News
    "https://www.marketwatch.com/rss/topstories",                  # ✅ Existing
    "https://www.fool.com/feeds/index.aspx",                       # ✅ Existing
    "https://www.zerohedge.com/fullrss.xml"                        # ✅ Existing
]

# === Templates to Turn News into Beliefs ===
TEMPLATES = [
    "I believe {headline}. Summary: {summary}",
    "News just broke: {headline} — {summary}",
    "What might happen after this? {headline}. Details: {summary}",
    "Should I trade based on this? {headline}. Context: {summary}"
]

# === Fallback Beliefs in Case News Fails ===
FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

# === Convert Title + Summary into Belief Prompt ===
def generate_belief_prompt(title, summary=""):
    return random.choice(TEMPLATES).format(
        headline=title.strip(),
        summary=summary.strip()[:200] or "No summary provided"
    )

# === Fetch News from Each RSS Feed ===
def fetch_news_entries(limit_per_feed=5):
    entries = []
    for url in RSS_FEEDS:
        try:
            print(f"🔗 Fetching from: {url}")
            feed = feedparser.parse(url)
            if not feed.entries:
                raise ValueError("No entries returned")
            print(f"✅ Parsed {len(feed.entries)} entries from {url}")
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and len(title) > 20:
                    entries.append((title, summary))
            # Debug: print actual headlines found
            print(f"📥 Titles: {[e.get('title') for e in feed.entries[:limit_per_feed]]}")
        except Exception as e:
            print(f"⚠️ Feed error: {url} → {e}")
    return entries

# === Save Belief for Model Review ===
def log_raw_belief(title, summary, belief):
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    try:
        with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])
    except Exception as e:
        print(f"❌ Logging raw belief error: {e}")

# === Save to Training Data if Strategy is Returned ===
def log_training_row(belief, strategy, asset_class):
    try:
        with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([belief, strategy, asset_class])
    except Exception as e:
        print(f"❌ Training log error: {e}")

# === Send Belief to FastAPI Backend ===
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

# === Main Loop: Fetches → Converts → Sends to Backend ===
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
            print(f"✅ Proceeding with {len(entries)} fresh headlines.")
            for title, summary in entries:
                belief = generate_belief_prompt(title, summary)
                send_belief_to_backend(belief, title, summary)

        print(f"⏲️ Sleeping {interval} sec...\n")
        time.sleep(interval)

# === Run When Executed Directly ===
if __name__ == "__main__":
    run_news_ingestor()
