"""
GPT-Powered News Ingestor:
Fetches RSS news → uses GPT to generate belief + metadata →
POSTs to backend → logs → triggers retraining.
"""

import feedparser
import openai
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

openai.api_key = os.getenv("OPENAI_API_KEY")

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
    entries = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:limit_per_feed]:
                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", entry.get("description", "")).strip()
                    if title and len(title) > 20:
                        entries.append((title, summary))
        except Exception as e:
            print(f"⚠️ Feed error from {url}: {e}", file=sys.stderr)
    return entries

def generate_gpt_belief(title, summary):
    prompt = (
        f"Based on the following news:\n\n"
        f"Title: {title}\n"
        f"Summary: {summary[:300]}\n\n"
        "Extract a belief suitable for a trading engine. Then determine:\n"
        "- direction (bullish, bearish, neutral)\n"
        "- confidence (0 to 1)\n"
        "- asset_class (stock, ETF, bond, crypto, etc)\n"
        "- tags (comma-separated list of relevant themes or sectors)\n\n"
        "Return as JSON like:\n"
        "{ \"belief\": \"...\", \"direction\": \"bullish\", \"confidence\": 0.8, \"asset_class\": \"stock\", \"tags\": [\"AI\", \"Tech\"] }"
    )

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        parsed = response.choices[0].message.content.strip()
        return eval(parsed) if parsed.startswith("{") else {"belief": title}
    except Exception as e:
        print(f"❌ GPT error: {e}", file=sys.stderr)
        return {"belief": title}

def log_raw_belief(title, summary, belief):
    os.makedirs(os.path.dirname(RAW_LOG_PATH), exist_ok=True)
    with open(RAW_LOG_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([datetime.datetime.now().isoformat(), title, summary, belief])

def log_training_row(belief, strategy, asset_class):
    with open(TRAINING_PATH, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([belief, strategy, asset_class])

def send_to_backend(data):
    try:
        r = requests.post(BACKEND_URL, json=data)
        if r.status_code == 200:
            response = r.json()
            strategy = response.get("strategy", {}).get("type", "unknown")
            asset_class = response.get("asset_class", data.get("asset_class", "unknown"))
            print(f"✅ Strategy generated: {data['belief'][:60]}...", file=sys.stderr)
            log_training_row(data["belief"], strategy, asset_class)
        else:
            print(f"❌ Backend error {r.status_code}: {data['belief'][:60]}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Request error: {e}", file=sys.stderr)

def trigger_retraining():
    try:
        response = requests.post(RETRAIN_URL)
        if response.status_code == 200:
            print("🔁 Retraining triggered", file=sys.stderr)
        else:
            print(f"❌ Retrain failed — Status: {response.status_code}", file=sys.stderr)
    except Exception as e:
        print(f"❌ Retrain exception: {e}", file=sys.stderr)

def run_news_ingestor():
    print(f"\n🚀 GPT News Ingestor started: {datetime.datetime.now()}", file=sys.stderr)
    entries = fetch_news_entries()
    print(f"📰 News fetched: {len(entries)}", file=sys.stderr)

    if not entries:
        fallback = random.choice(FALLBACK_BELIEFS)
        print("⚠️ No news — using fallback belief", file=sys.stderr)
        send_to_backend({"belief": fallback})
        write_training_log("📰 News fetched: 0\n🧠 Beliefs generated: 1\n➕ New beliefs added: 1")
    else:
        for title, summary in entries:
            data = generate_gpt_belief(title, summary)
            send_to_backend(data)
            log_raw_belief(title, summary, data["belief"])
        write_training_log(
            f"📰 News fetched: {len(entries)}\n🧠 Beliefs generated: {len(entries)}\n➕ New beliefs added: {len(entries)}"
        )

    trigger_retraining()
    print(f"✅ GPT News Ingestor completed at {datetime.datetime.now()}", file=sys.stderr)

# === Entrypoint ===
if __name__ == "__main__":
    run_news_ingestor()
