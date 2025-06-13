# theme_map.py
# Maps user-specified themes (e.g., "AI", "clean energy") to relevant tickers or ETFs

def match_theme(text):
    """
    Match known investment themes to tickers.
    If no known theme is found, fallback to default ETF.
    """

    text = text.lower()

    themes = {
        "ai": ["NVDA", "MSFT", "AAPL", "QQQ"],
        "technology": ["AAPL", "MSFT", "GOOG", "QQQ"],
        "clean energy": ["ICLN", "TSLA", "ENPH", "NOVA"],
        "oil": ["XOM", "CVX", "OXY", "XLE"],
        "inflation": ["GLD", "TLT", "TIP"],
        "dividends": ["SCHD", "VYM", "HDV"],
        "emerging markets": ["VWO", "EEM", "BABA"],
        "crypto": ["COIN", "RIOT", "MARA"],
        "china": ["BABA", "KWEB", "JD"],
        "semiconductors": ["NVDA", "AMD", "SMH", "AVGO"],
        "real estate": ["VNQ", "PLD", "O", "SPG"],
        "defense": ["LMT", "RTX", "NOC", "XAR"],
        "banks": ["JPM", "BAC", "XLF", "GS"],
        "bonds": ["TLT", "IEF", "BND"],
        "commodities": ["GLD", "SLV", "DBC"],
        "metaverse": ["META", "RBLX", "U"],
        "healthcare": ["XLV", "JNJ", "UNH", "PFE"],
        "consumer staples": ["XLP", "KO", "PG", "WMT"],
        "consumer discretionary": ["XLY", "AMZN", "TSLA", "MCD"],
        "index": ["SPY", "QQQ", "DIA"],
    }

    for theme, tickers in themes.items():
        if theme in text:
            return tickers[0]  # Return top-matching ticker
    return "SPY"  # Default fallback if no match
