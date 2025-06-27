# backend/news_ingestor.py

"""
This script fetches financial news from various RSS feeds,
parses headline + summary, converts them to belief-style prompts,
and sends them to the MarketPlayground backend for AI ingestion.
Designed to run continuously as a Render background worker.
"""

import feedparser
import random
import requests
import time

# Backend endpoint (Render URL or localhost for dev)
BACKEND_URL = "https://marketplayground-backend.onrender.com/process_belief"

# RSS feeds to pull from
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",  # WSJ
    "https://www.investing.com/rss/news.rss",         # Investing.com
    "https://www.marketwatch.com/rss/topstories",     # MarketWatch
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC
]

# Convert RSS entry to structured belief prompt
def generate_belief_prompt(title: str, summary: str = "") -> str:
    templates = [
        "I believe {headline}. Summary: {summary}",
        "News just broke: {headline} — {summary}",
        "What might happen after this? {headline}. Details: {summary}",
        "Should I trade based on this? {headline}. Context: {summary}"
    ]
    return random.choice(templates).format(
        headline=title.strip(),
        summary=summary.strip()[:200]  # limit to 200 chars
    )

# Fetch headlines and summaries
def fetch_news_entries(limit_per_feed: int = 5):
    entries = []
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:limit_per_feed]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", "").strip()
            if title and len(title) > 20:
                entries.append((title, summary))
    return entries

# Send belief to backend
def send_belief_to_backend(belief: str):
    try:
        response = requests.post(BACKEND_URL, json={"belief": belief})
        if response.status_code == 200:
            print(f"✅ Processed: {belief[:60]}...")
        else:
            print(f"⚠️ Failed ({response.status_code}): {belief[:60]}...")
    except Exception as e:
        print(f"❌ Error sending belief: {e}")

# Main loop (runs forever, every 15 min)
def run_news_ingestor(interval=900):
    while True:
        print("📰 Fetching fresh financial news...")
        entries = fetch_news_entries()
        print(f"🔍 Found {len(entries)} entries")

        for title, summary in entries:
            belief = generate_belief_prompt(title, summary)
            send_belief_to_backend(belief)

        print(f"⏲️ Sleeping for {interval} seconds...")
        time.sleep(interval)

if __name__ == "__main__":
    run_news_ingestor()
