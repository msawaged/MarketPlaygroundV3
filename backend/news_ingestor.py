# backend/news_ingestor.py

"""
News Ingestor:
Fetches RSS headlines → generates belief → sends to backend →
logs strategy locally and to Supabase → triggers model retraining.
Includes debug logging for Render background tracing.
"""

import feedparser
import requests
import datetime
import os
import csv
import random
import sys
import time
from utils.logger import write_training_log

# === 🔐 Supabase Configuration ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_TABLE = "news_beliefs"

# === 🔧 Backend URLs ===
BACKEND_URL = "https://marketplayground-backend.onrender.com/strategy/process_belief"
RETRAIN_URL = "https://marketplayground-backend.onrender.com/force_retrain"
FEEDBACK_URL = "https://marketplayground-backend.onrender.com/feedback/submit_feedback"

# === 📁 File Paths ===
RAW_LOG_PATH = "backend/logs/news_beliefs.csv"
TRAINING_PATH = "backend/Training_Strategies.csv"
DEBUG_LOG_PATH = "backend/logs/news_ingestor_debug.log"

# === 📰 RSS Sources ===
RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.fool.com/feeds/index.aspx",
    "https://www.zerohedge.com/fullrss.xml",
    "https://www.investing.com/rss/news_25.rss",
    "https://www.bloomberg.com/feed/podcast/etf-report",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"
]

# === 💭 Fallback Beliefs ===
FALLBACK_BELIEFS = [
    "I believe the market may react to rising uncertainty.",
    "Should I buy energy stocks due to inflation?",
    "Is the AI bubble bursting this quarter?",
    "What will the Fed do after this recent volatility?",
    "Is gold a safe haven again in this climate?"
]

def log_debug(msg: str):
    os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(DEBUG_LOG_PATH, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def fetch_news_entries(limit_per_feed=5):
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
            log_debug(f"🚨 Feed error from {url}: {e}")
    return entries

def log_raw_belief(title, summary, belief):
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    with open(RAW_LOG_PATH, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])

def log_training_row(belief, strategy, asset_class):
    with open(TRAINING_PATH, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([belief, strategy, asset_class])

# ✅ FIXED: Changed "positive" → "good" to pass feedback schema
def submit_auto_feedback(belief, strategy_type, confidence=0.5):
    feedback_payload = {
        "belief": belief,
        "strategy": strategy_type,
        "feedback": "good",  # ✅ Must be "good" or "bad"
        "user_id": "news_ingestor",
        "source": "news_ingestor",
        "confidence": confidence
    }
    print(f"\n📤 Submitting feedback payload:\n{feedback_payload}\n")

    try:
        r = requests.post(FEEDBACK_URL, json=feedback_payload, timeout=10)
        if r.status_code == 200:
            log_debug(f"🧠 Auto-feedback submitted for: {belief[:60]}")
        else:
            log_debug(f"⚠️ Feedback failed: {r.status_code} — {r.text}")
    except Exception as e:
        log_debug(f"⚠️ Feedback exception: {e}")

def send_to_backend(belief_text):
    payload = {"belief": belief_text, "user_id": "news_ingestor"}
    for attempt in range(2):  # 🔁 Max 2 tries
        try:
            r = requests.post(BACKEND_URL, json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                strategy = data.get("strategy", {}).get("type", "unknown")
                asset_class = data.get("asset_class", "unknown")
                confidence = data.get("confidence", 0.5)
                log_training_row(belief_text, strategy, asset_class)
                log_debug(f"✅ Strategy generated: {strategy} → {belief_text[:60]}")
                submit_auto_feedback(belief_text, strategy, confidence)
                return True
            else:
                log_debug(f"❌ Backend error {r.status_code}: {r.text}")
        except Exception as e:
            log_debug(f"❌ Backend request failed (attempt {attempt+1}): {e}")
            time.sleep(2)
    return False

def write_news_belief_to_supabase(title, summary, belief):
    if not SUPABASE_URL or not SUPABASE_KEY:
        log_debug("⚠️ Supabase credentials missing. Skipping cloud save.")
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
            json=payload,
            timeout=10
        )
        if r.status_code not in [200, 201, 204]:
            log_debug(f"⚠️ Supabase insert failed: {r.status_code} — {r.text}")
    except Exception as e:
        log_debug(f"⚠️ Supabase exception: {e}")

def trigger_retraining():
    try:
        r = requests.post(RETRAIN_URL, timeout=10)
        if r.status_code == 200:
            log_debug("🔁 Retraining triggered")
        else:
            log_debug(f"❌ Retraining failed: {r.status_code}")
    except Exception as e:
        log_debug(f"❌ Retraining exception: {e}")

def run_news_ingestor():
    now = datetime.datetime.now()
    log_debug(f"\n🚀 News Ingestor started: {now}")
    print(f"🚀 News Ingestor started: {now}", file=sys.stderr)

    try:
        entries = fetch_news_entries()
        log_debug(f"📰 News fetched: {len(entries)}")

        if not entries:
            fallback = random.choice(FALLBACK_BELIEFS)
            log_debug("⚠️ No entries — using fallback belief")
            send_to_backend(fallback)
            write_training_log("📰 News fetched: 0\n🧠 Beliefs generated: 1\n➕ New beliefs added: 1")
        else:
            for i, (title, summary) in enumerate(entries):
                belief = f"{title}. {summary[:150]}"
                log_raw_belief(title, summary, belief)
                write_news_belief_to_supabase(title, summary, belief)

                log_debug(f"🧠 [{i+1}/{len(entries)}] Sending: {belief[:60]}")
                send_to_backend(belief)
                time.sleep(5)  # ⏱️ Slow down to avoid backend overload

            write_training_log(
                f"📰 News fetched: {len(entries)}\n🧠 Beliefs generated: {len(entries)}\n➕ New beliefs added: {len(entries)}"
            )

        trigger_retraining()
        log_debug(f"✅ News Ingestor completed: {datetime.datetime.now()}")

    except Exception as e:
        log_debug(f"❌ Top-level crash: {e}")
        print(f"❌ Fatal Error: {e}", file=sys.stderr)

# === CLI Entry Point ===
if __name__ == "__main__":
    run_news_ingestor()
