# backend/news_ingestor.py
"""
News Ingestor:
Fetches RSS headlines → generates belief → sends to backend →
logs strategy locally and to Supabase → triggers model retraining.
"""

import feedparser        # Parses RSS feeds
import requests          # For HTTP calls to backend and Supabase
import datetime
import os
import csv
import random
import sys

from utils.logger import write_training_log  # For centralized training event logs

# === 🔐 Supabase Configuration ===
SUPABASE_URL = os.getenv("SUPABASE_URL")                         # Supabase project URL
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")           # Supabase service role key (secure)
SUPABASE_TABLE = "news_beliefs"                                 # Table to store parsed news beliefs

# === 🔧 Backend URLs ===
BACKEND_URL = "https://marketplayground-backend.onrender.com/strategy/process_belief"
RETRAIN_URL = "https://marketplayground-backend.onrender.com/force_retrain"

# === 📁 Local File Paths ===
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"                  # CSV backup of parsed beliefs
TRAINING_PATH = "backend/Training_Strategies.csv"               # Strategy training data CSV

# === 📰 RSS Feed Sources ===
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.zerohedge.com/fullrss.xml"
]

# === 💭 Fallback Beliefs (used if no news available) ===
FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

def fetch_news_entries(limit_per_feed=5):
    """
    Parses all RSS feeds and returns a list of (title, summary) tuples.
    Filters out short titles or broken feeds.
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
    Appends a raw belief (title + summary → belief) to local CSV as backup.
    """
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])

def log_training_row(belief, strategy, asset_class):
    """
    Logs belief-strategy-asset class triple to the training data CSV.
    Used later for retraining the ML model.
    """
    with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([belief, strategy, asset_class])

def send_to_backend(belief_text):
    """
    Sends belief to backend for strategy generation.
    Logs the result locally for retraining.
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

def write_news_belief_to_supabase(title, summary, belief):
    """
    Pushes belief record to Supabase `news_beliefs` table.
    Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to be set.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("⚠️ Supabase ENV not set. Skipping cloud sync.", file=sys.stderr)
        return

    try:
        payload = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "title": title,
            "summary": summary,
            "belief": belief
        }

        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload
        )

        if r.status_code not in [200, 201, 204]:
            print(f"⚠️ Supabase insert failed ({r.status_code}): {r.text}", file=sys.stderr)

    except Exception as e:
        print(f"⚠️ Supabase exception: {e}", file=sys.stderr)

def trigger_retraining():
    """
    Calls the backend retrain endpoint to initiate model refresh.
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
    Main entrypoint:
    - Fetch news
    - Turn into beliefs
    - Send to backend
    - Save to Supabase and logs
    - Trigger model retraining
    """
    print(f"\n🚀 News Ingestor started: {datetime.datetime.now()}", file=sys.stderr)
    entries = fetch_news_entries()
    print(f"📰 News fetched: {len(entries)}", file=sys.stderr)

    if not entries:
        # If no entries are available, send a fallback belief
        fallback = random.choice(FALLBACK_BELIEFS)
        print("⚠️ No news — using fallback belief", file=sys.stderr)
        send_to_backend(fallback)
        write_training_log("📰 News fetched: 0\n🧠 Beliefs generated: 1\n➕ New beliefs added: 1")
    else:
        # Loop through each entry and process it
        for title, summary in entries:
            belief = f"{title}. {summary[:150]}"
            send_to_backend(belief)                      # Send to AI engine
            log_raw_belief(title, summary, belief)       # Local CSV backup
            write_news_belief_to_supabase(title, summary, belief)  # Cloud sync

        # Final training log entry
        write_training_log(
            f"📰 News fetched: {len(entries)}\n🧠 Beliefs generated: {len(entries)}\n➕ New beliefs added: {len(entries)}"
        )

    trigger_retraining()
    print(f"✅ News Ingestor completed at {datetime.datetime.now()}", file=sys.stderr)

# === Run the ingestor when file is executed directly ===
if __name__ == "__main__":
    run_news_ingestor()
