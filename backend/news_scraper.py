# backend/news_scraper.py

import os
import json
import feedparser
from datetime import datetime
from backend.news_entity_parser import extract_entities_from_belief

# RSS feeds to try
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.investing.com/rss/news_25.rss",
]

SAVE_PATH = "backend/news_beliefs.json"
FALLBACK_PATH = "backend/news_sample_fallback.json"

def fetch_from_rss():
    print()
    beliefs = []
    for url in RSS_FEEDS:
        print(f"📡 Fetching: {url}")
        feed = feedparser.parse(url)
        if not feed.entries:
            print("⚠️ No entries found.")
            continue

        for entry in feed.entries:
            title = entry.get("title", "")
            published = entry.get("published", str(datetime.utcnow()))
            parsed = extract_entities_from_belief(title)
            belief_entry = {
                "belief": title,
                "published": published,
                "entities": parsed,
            }
            beliefs.append(belief_entry)

    return beliefs

def fetch_news_beliefs():
    beliefs = fetch_from_rss()

    if not beliefs:
        print("\n⚠️ RSS failed — using fallback file.")
        if os.path.exists(FALLBACK_PATH):
            with open(FALLBACK_PATH, "r") as f:
                beliefs = json.load(f)
        else:
            print("❌ No fallback file found.")
            beliefs = []

    with open(SAVE_PATH, "w") as f:
        json.dump(beliefs, f, indent=2)

    print(f"\n✅ Saved {len(beliefs)} beliefs to {SAVE_PATH}")
    return beliefs

# Run standalone
if __name__ == "__main__":
    fetch_news_beliefs()
