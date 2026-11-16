"""Ticker identity check: is this ticker still the company the idea names?

Tickers get reused (PARA was Paramount until Aug 2025; today it is Parabolic Technologies) and Claude sometimes
pairs a company with the wrong ticker (Philip Morris -> PMI, which is Picard Medical; BYD -> Boyd Gaming). The app
used to trust the ticker alone, so a "Paramount" idea was shown, priced and graded as a penny stock.

`same_company(claude_name, alpaca_name, ticker)` compares the two names with plain rules (shared word, one word the
start of the other, initials such as ADP / IBM / onsemi) plus a short list of well-known renames. It errs toward
keeping a pick: an empty name on either side always passes. Checked on 1,439 live (ticker, Claude name, Alpaca
name) pairs on 2026-11-16: it drops the ~25 real misreads found and keeps the renames/abbreviations.
"""
from __future__ import annotations

import re

# Legal-form, share-class and listing words, fund issuers and very generic corporate words: never evidence of a match.
STOP = frozenset("""
the a an and of de du la le inc incorporated corp corporation co company companies cos ltd limited plc llc lp l p
sa s a b c n v nv ag se spa sab cv bv kk oyj asa ab group holding holdings international intl global worldwide
technologies technology systems industries enterprises class common stock stocks share shares ordinary unit units
american depositary depository receipt receipts ads adr each representing right receive series new
etf etfs fund funds trust index portfolio shs ii iii iv us usa
ishares spdr vanguard invesco proshares direxion wisdomtree vaneck schwab state street first ark amplify
""".split())

# Former / everyday names Claude still uses for a ticker whose official name changed (word overlap can't see these).
ALIASES = {
    "SLB": "schlumberger", "IREN": "iris energy", "POWW": "ammo", "MARA": "marathon digital",
    "MSTR": "microstrategy", "WAB": "westinghouse air brake", "META": "facebook", "GOOGL": "google",
    "GOOG": "google", "BKNG": "priceline", "GE": "general electric", "RTX": "raytheon", "WBD": "warner",
    "BRK.B": "berkshire", "BRK.A": "berkshire", "XYZ": "block square",
    "QQQ": "nasdaq", "QQQM": "nasdaq", "DIA": "dow jones", "IWM": "russell", "VTI": "total market",
    "CARZ": "nasdaq global auto", "SQ": "block square",
}


def _words(name: str) -> list[str]:
    s = re.sub(r"\(.*?\)", lambda m: " " + m.group(0)[1:-1] + " ", (name or "").lower())  # keep words in brackets
    s = s.replace("&", " and ")
    return [w for w in re.split(r"[^a-z0-9]+", s) if w]


def _core(name: str) -> list[str]:
    return [w for w in _words(name) if len(w) >= 2 and w not in STOP and not w.isdigit()]


def _initials(words: list[str]) -> str:
    return "".join(w[0] for w in words if w)


def same_company(claude_name: str, alpaca_name: str, ticker: str = "") -> bool:
    """True unless the two names clearly describe different companies (see module docstring)."""
    if not (claude_name or "").strip() or not (alpaca_name or "").strip():
        return True
    cw, aw = _core(claude_name), _core(alpaca_name)
    if not cw or not aw:  # e.g. Claude just wrote "Inc." or only generic words: nothing to compare
        return True
    alias = ALIASES.get((ticker or "").upper())
    if alias and set(_core(alias)) & set(cw):
        return True
    for c in cw:
        for a in aw:
            if c == a and len(c) >= 2:
                return True
            short, long_ = (c, a) if len(c) <= len(a) else (a, c)
            if len(short) >= 4 and long_.startswith(short):  # financial / financials, MARA / Marathon
                return True
            if len(short) >= 5 and short in long_:  # Strategy / MicroStrategy
                return True
    cj, aj = "".join(cw), "".join(aw)
    if len(cj) >= 4 and (aj.startswith(cj) or cj.startswith(aj) and len(aj) >= 4):  # onsemi / ON Semiconductor
        return True
    # initials: "ADP" / Automatic Data Processing, "UEC" / Uranium Energy Corp, "TSMC", "GE" / General Electric
    a_all = _initials(_words(alpaca_name))
    for c in cw:
        if len(c) >= 2 and (a_all.startswith(c) or _initials(aw).startswith(c)):
            return True
    for a in aw:
        if len(a) >= 2 and _initials(cw) == a:
            return True
        if len(_initials(cw)) >= 3 and a.startswith(_initials(cw)):  # Westinghouse Air Brake Tech. / Wabtec
            return True
    return False
