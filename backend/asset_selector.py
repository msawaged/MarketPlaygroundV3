# asset_selector.py
# Determines best asset class + tickers based on belief text

theme_to_assets = {
    "ai":               ("stock", ["NVDA", "MSFT", "GOOGL", "SMCI"]),
    "robotics":         ("etf", ["BOTZ", "ROBO", "IRBT"]),
    "semiconductors":   ("stock", ["NVDA", "AMD", "AVGO", "INTC"]),
    "clean energy":     ("etf", ["ICLN", "ENPH", "PLUG"]),
    "china tech":       ("etf", ["KWEB", "BABA", "JD", "PDD"]),
    "crypto":           ("crypto", ["BTC-USD", "ETH-USD"]),
    "value":            ("stock", ["BRK.B", "JNJ", "KO"]),
    "diversified":      ("etf", ["SPY", "QQQ", "VTI"]),
    "tech":             ("etf", ["QQQ", "XLK", "VGT"]),
    "growth":           ("stock", ["TSLA", "AMZN", "NVDA"]),
    "finance":          ("etf", ["XLF", "JPM", "GS"]),
    "bonds":            ("etf", ["TLT", "IEF", "BND"]),
}

fallback_default = {
    "asset_class": "stock",
    "tickers": ["AAPL"]
}

def select_assets_from_belief(text):
    text = text.lower()

    for theme, (asset_class, tickers) in theme_to_assets.items():
        if theme in text:
            return {
                "asset_class": asset_class,
                "tickers": tickers
            }

    return fallback_default
