# backend/news_ingestor.py

"""
Fetches financial news from multiple RSS feeds, cleans headlines,
and transforms them into belief-style inputs for AI ingestion.
"""

import feedparser
import random
from typing import List

# List of RSS feeds (you can add more!)
RSS_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",      # WSJ Markets
    "https://www.investing.com/rss/news.rss",             # Investing.com
    "https://www.marketwatch.com/rss/topstories",         # MarketWatch
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
]

def fetch_rss_headlines() -> List[str]:
    headlines = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:  # Limit per feed
            title = entry.title.strip()
            if title and len(title) > 20:
                headlines.append(title)
    return headlines

def convert_headlines_to_beliefs(headlines: List[str]) -> List[str]:
    """
    Adds natural tone or context to turn headlines into AI beliefs.
    """
    belief_templates = [
        "I think {headline}",
        "Based on the news: {headline}",
        "This just happened → {headline}",
        "What does this mean for markets: {headline}",
        "Should I act on this? {headline}"
    ]
    beliefs = [
        random.choice(belief_templates).format(headline=headline)
        for headline in headlines
    ]
    return beliefs

def get_news_beliefs(n: int = 10) -> List[str]:
    """
    Returns a list of up to `n` belief-style statements from real news.
    """
    headlines = fetch_rss_headlines()
    random.shuffle(headlines)
    beliefs = convert_headlines_to_beliefs(headlines)
    return beliefs[:n]

# For testing directly
if __name__ == "__main__":
    for belief in get_news_beliefs():
        print("📰", belief)
