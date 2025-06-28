# backend/news_ingestor.py

"""
Robust News Ingestor: Fetches RSS headlines → formats belief → sends to backend.
Runs locally or on Render. Now with fallback logic and 10 RSS sources.
"""

import feedparser
import random
import requests
import time
import datetime

BACKEND_URL = "https://marketplayground-backend.onrender.com/process_belief"

RSS_FEEDS = [
    "https://www.bloomberg.com/feed/podcast/etf-report.xml",  # ✅ Replaced WSJ with working Bloomberg feed
    "https://www.marketwatch.com/rss/topstories",             # MarketWatch
    "https://www.cnbc.com/id/100003114/device/rss/rss.xml",   # CNBC
    "https://www.investing.com/rss/news.rss",                 # Investing.com
    "https://www.fxstreet.com/rss/news",                      # FXStreet
    "https://www.nasdaq.com/feed/rssoutbound?category=Market%20News", # Nasdaq
    "https://www.reutersagency.com/feed/?best-sectors=business-finance", # Reuters
    "https://www.fool.com/feeds/index.aspx",                  # Motley Fool
    "https://www.zerohedge.com/fullrss.xml",                  # ZeroHedge
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
            feed = feedparser.parse(url)
            print(f"🌐 {url} → {len(feed.entries)} entries")  # ✅ DEBUG PER FEED
            for entry in feed.entries[:limit_per_feed]:
                title = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                if title and len(title) > 20:
                    entries.append((title, summary))
        except Exception as e:
            print(f"⚠️ Feed error: {url} → {e}")
    return entries

def send_belief_to_backend(belief):
    try:
        r = requests.post(BACKEND_URL, json={"belief": belief})
        if r.status_code == 200:
            print(f"✅ Sent: {belief[:60]}...")
        else:
            print(f"❌ Backend error ({r.status_code}): {belief[:60]}")
    except Exception as e:
        print(f"❌ Request error: {e}")

def run_news_ingestor(interval=900):
    while True:
        print(f"\n📰 [{datetime.datetime.now()}] News Ingestor Running")
        entries = fetch_news_entries()
        print(f"🔍 Found {len(entries)} headlines")

        if not entries:
            fallback = random.choice(FALLBACK_BELIEFS)
            print("⚠️ No headlines, using fallback")
            send_belief_to_backend(fallback)
        else:
            for title, summary in entries:
                belief = generate_belief_prompt(title, summary)
                send_belief_to_backend(belief)

        print(f"⏲️ Sleeping {interval} sec...\n")
        time.sleep(interval)

if __name__ == "__main__":
    run_news_ingestor()
