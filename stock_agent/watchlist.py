"""Your personal watchlist, organised as the 'triangle' from class.

    Base   (~60%) — foundation holds, 2-3 years
    Middle (~30%) — cyclical AI / robotics / space, 3-12 months
    Top           — special situations, short-lived

These tickers get scanned alongside the default large-cap universe and are
grouped by tier on the dashboard. Edit this file to change what you track.

Note: SpaceX is private and not tradable, so it can't be included here.
"""

# Tier -> (blurb, tickers). Order is Base, Middle, Top.
TRIANGLE = {
    "Base": {
        "blurb": "~60% · foundation · hold 2-3 years",
        "tickers": ["GOOG", "MU", "AMZN", "NVDA"],
    },
    "Middle": {
        "blurb": "~30% · cyclical AI / robotics / space · hold 3-12 months",
        "tickers": ["IREN", "NBIS", "MRVL", "JOBY", "RKLB", "FSLR", "LITE", "COHR", "CRS", "PL"],
    },
    "Top": {
        "blurb": "special situations · short-lived",
        "tickers": ["LULU", "NKE"],
    },
}


def watchlist_tickers():
    """Every ticker in the triangle, de-duplicated, order preserved."""
    seen, out = set(), []
    for tier in TRIANGLE.values():
        for t in tier["tickers"]:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def tier_for(ticker: str):
    """Return the tier name a ticker belongs to, or None."""
    ticker = ticker.upper()
    for name, tier in TRIANGLE.items():
        if ticker in tier["tickers"]:
            return name
    return None
