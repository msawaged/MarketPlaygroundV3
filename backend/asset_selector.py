# backend/asset_selector.py

"""
This module detects which asset class (stocks, ETFs, bonds, crypto, etc.)
is most relevant based on the user's belief or strategy goal.
"""

def detect_asset_class(belief: str) -> str:
    """
    Infers asset class from the belief text.

    Parameters:
        belief (str): User's belief input (e.g., "the market will tank")

    Returns:
        str: One of ['stocks', 'etfs', 'bonds', 'crypto', 'currencies']
    """
    belief = belief.lower()

    if any(term in belief for term in ['stock', 'equity', 'company', 'share']):
        return 'stocks'
    elif any(term in belief for term in ['etf', 'index fund', 'spy', 'qqq', 'iwm']):
        return 'etfs'
    elif any(term in belief for term in ['bond', 'yield', 'treasury']):
        return 'bonds'
    elif any(term in belief for term in ['bitcoin', 'crypto', 'ethereum', 'altcoin']):
        return 'crypto'
    elif any(term in belief for term in ['forex', 'currency', 'dollar', 'euro', 'yen']):
        return 'currencies'
    else:
        return 'stocks'  # default fallback
