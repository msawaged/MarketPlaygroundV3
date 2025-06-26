# backend/news_entity_parser.py

"""
Parses financial news beliefs to extract entities, sentiment direction,
topics, and company names using spaCy NLP.
"""

import spacy

# Load English language model
nlp = spacy.load("en_core_web_sm")

# Keywords to detect directional sentiment
UP_KEYWORDS = ["rally", "jump", "gain", "rise", "increase", "soar", "boost"]
DOWN_KEYWORDS = ["drop", "fall", "decline", "crash", "sink", "plunge", "cut"]

def extract_entities_from_belief(text: str) -> dict:
    """
    Extracts company names, countries, and inferred sentiment direction
    from a given belief string.
    """
    doc = nlp(text)

    companies = []
    countries = []
    sentiment = "neutral"
    direction_score = 0

    # Named Entity Recognition
    for ent in doc.ents:
        if ent.label_ == "ORG":
            companies.append(ent.text)
        elif ent.label_ == "GPE":
            countries.append(ent.text)

    # Directional scoring from keywords
    lower_text = text.lower()
    for word in UP_KEYWORDS:
        if word in lower_text:
            direction_score += 1
    for word in DOWN_KEYWORDS:
        if word in lower_text:
            direction_score -= 1

    if direction_score > 0:
        sentiment = "bullish"
    elif direction_score < 0:
        sentiment = "bearish"

    return {
        "companies": list(set(companies)),
        "countries": list(set(countries)),
        "sentiment": sentiment
    }

# 🔍 Test this module standalone
if __name__ == "__main__":
    sample = "Nvidia shares plunge after China AI crackdown spooks tech sector."
    result = extract_entities_from_belief(sample)
    print("🧠 Parsed Belief Info:", result)
