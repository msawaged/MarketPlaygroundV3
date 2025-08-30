# backend/utils/ticker_sanitizer.py
from typing import Optional

# Common English words that often show up as false "tickers"
COMMON_WORDS = {
    "I","ME","MY","WE","YOU","THEY","IT","OUR","YOUR","THE","A","AN","OF","IN","ON","AT",
    "TO","FOR","WITH","IF","AND","OR","BUT","UP","DOWN","BUY","SELL","CALL","PUT",
    "GO","GOING","WILL","MADE","MAKE","MAKING","MONEY","PRICE","PRICES","SOON"
}

# 1-letter symbols that are actually tradable on major US exchanges
ONE_LETTER_WHITELIST = {"F","T","C","A","B","K","M","X"}  # adjust if needed

OIL_KEYWORDS = ("oil","crude","wti","brent")
OIL_ETF = "USO"  # could later expand to map {"brent": "BNO", "wti": "USO"}

def sanitize_ticker(tok: str) -> Optional[str]:
    """Return a cleaned, plausible ticker or None."""
    if not tok:
        return None
    t = tok.upper().strip("$.,:;!?()[]{}\"'")
    if not t.isascii() or not t.replace("-", "").isalnum():
        return None
    if t in COMMON_WORDS:
        return None
    if len(t) == 1 and t not in ONE_LETTER_WHITELIST:
        return None
    return t

def finalize_detected_ticker(cleaned_belief: str,
                             initial_ticker: Optional[str],
                             asset_class: Optional[str]) -> Optional[str]:
    """
    1) Sanitize the initial detected ticker.
    2) If none left and belief mentions oil, route to USO for ETF/options.
    """
    # 1) sanitize
    t = sanitize_ticker(initial_ticker) if initial_ticker else None

    # 2) oil router (only when ETF/options/unspecified)
    if not t and any(k in cleaned_belief.lower() for k in OIL_KEYWORDS):
        if (asset_class or "").lower() in {"etf", "options", ""}:
            return OIL_ETF

    return t
