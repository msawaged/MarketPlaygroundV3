# tagger.py
# 🔍 Enhances AI-generated tags with sentiment logic

def enrich_tags(tags, sentiment):
    """
    Adjust tags based on sentiment for better strategy alignment.
    """
    tags = tags.copy()

    # Direction override
    if sentiment == "bullish":
        tags["direction"] = "bullish"
    elif sentiment == "bearish":
        tags["direction"] = "bearish"
    else:
        tags["direction"] = tags.get("direction", "neutral")

    # Optional: Add more refinements here
    if "duration" not in tags:
        tags["duration"] = "short"

    if "volatility" not in tags:
        tags["volatility"] = "medium"

    return tags
