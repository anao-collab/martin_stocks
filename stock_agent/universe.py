"""The universe of stocks the agent scans.

A curated list of ~50 liquid, well-known US large-caps spanning every major
sector. Kept deliberately small so a full scan runs in a few seconds and the
valuation comparisons have enough peers per sector to be meaningful.
"""

# Ticker -> the sector we expect it in. yfinance also reports a sector, but we
# keep our own mapping so peer-group comparisons stay stable even when a data
# point is missing.
LARGE_CAPS = [
    # Technology
    "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "AMD", "CSCO", "INTC",
    # Communication services
    "GOOGL", "META", "NFLX", "DIS", "TMUS", "VZ",
    # Consumer discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW",
    # Consumer staples
    "WMT", "COST", "PG", "KO", "PEP",
    # Financials
    "JPM", "BAC", "WFC", "GS", "MS", "V", "MA",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "PFE", "TMO",
    # Industrials
    "CAT", "BA", "GE", "HON", "UPS",
    # Energy
    "XOM", "CVX", "COP",
    # Utilities / real estate
    "NEE", "AMT",
]


def default_universe():
    """Return the default ticker list to scan."""
    return list(LARGE_CAPS)
