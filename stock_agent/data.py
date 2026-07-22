"""Market data fetching via yfinance, with a small on-disk cache.

yfinance is free and needs no API key. Its `.info` payload is generous but
individual fields are frequently missing, so every accessor here is written to
tolerate `None` and odd types rather than assume a field exists.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional

import yfinance as yf

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
CACHE_TTL_SECONDS = 60 * 30  # 30 minutes — market data doesn't move that fast intraday for our purposes


@dataclass
class Stock:
    """A snapshot of one company's fundamentals and recent price action."""

    ticker: str
    name: str
    sector: str
    industry: str
    price: Optional[float]
    currency: str
    market_cap: Optional[float]
    trailing_pe: Optional[float]
    forward_pe: Optional[float]
    peg: Optional[float]
    price_to_book: Optional[float]
    price_to_sales: Optional[float]
    dividend_yield: Optional[float]  # as a percent, e.g. 2.4 means 2.4%
    profit_margin: Optional[float]   # as a percent
    revenue_growth: Optional[float]  # as a percent, year-over-year
    earnings_growth: Optional[float]  # as a percent, year-over-year
    return_on_equity: Optional[float]  # as a percent
    target_mean_price: Optional[float]
    recommendation: Optional[str]
    fifty_two_week_high: Optional[float]
    fifty_two_week_low: Optional[float]
    day_change_pct: Optional[float]
    summary: str

    @property
    def analyst_upside_pct(self) -> Optional[float]:
        """Percent upside from current price to the mean analyst target."""
        if self.price and self.target_mean_price:
            return round((self.target_mean_price / self.price - 1) * 100, 1)
        return None

    @property
    def pct_of_52w_range(self) -> Optional[float]:
        """Where the price sits in its 52-week range: 0 = at the low, 100 = at the high."""
        if self.price and self.fifty_two_week_high and self.fifty_two_week_low:
            span = self.fifty_two_week_high - self.fifty_two_week_low
            if span > 0:
                return round((self.price - self.fifty_two_week_low) / span * 100, 1)
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["analyst_upside_pct"] = self.analyst_upside_pct
        d["pct_of_52w_range"] = self.pct_of_52w_range
        return d


def _num(value) -> Optional[float]:
    """Coerce a yfinance value to a float, or None if it isn't a usable number."""
    try:
        if value is None:
            return None
        f = float(value)
        # yfinance sometimes returns absurd sentinel values; treat them as missing.
        if f != f or f in (float("inf"), float("-inf")):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pct(value) -> Optional[float]:
    """yfinance reports ratios like margins/yields as fractions (0.024). Return a percent."""
    n = _num(value)
    return round(n * 100, 2) if n is not None else None


def _cache_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"{ticker.upper()}.json")


def _read_cache(ticker: str) -> Optional[Stock]:
    path = _cache_path(ticker)
    if not os.path.exists(path):
        return None
    if time.time() - os.path.getmtime(path) > CACHE_TTL_SECONDS:
        return None
    try:
        with open(path) as f:
            raw = json.load(f)
        # Only keep dataclass fields; computed properties are recomputed.
        fields = Stock.__dataclass_fields__.keys()
        return Stock(**{k: raw[k] for k in fields})
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _write_cache(stock: Stock) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(stock.ticker), "w") as f:
        json.dump(stock.to_dict(), f)


def fetch_stock(ticker: str, use_cache: bool = True) -> Optional[Stock]:
    """Fetch one stock's snapshot. Returns None if the ticker can't be resolved."""
    ticker = ticker.upper().strip()
    if use_cache:
        cached = _read_cache(ticker)
        if cached is not None:
            return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
    except Exception:
        return None

    if not info or info.get("regularMarketPrice") is None and info.get("currentPrice") is None:
        # yfinance returns a near-empty dict for bad tickers.
        return None

    price = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
    prev_close = _num(info.get("previousClose") or info.get("regularMarketPreviousClose"))
    day_change = None
    if price is not None and prev_close:
        day_change = round((price / prev_close - 1) * 100, 2)

    stock = Stock(
        ticker=ticker,
        name=info.get("shortName") or info.get("longName") or ticker,
        sector=info.get("sector") or "Unknown",
        industry=info.get("industry") or "Unknown",
        price=price,
        currency=info.get("currency") or "USD",
        market_cap=_num(info.get("marketCap")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        peg=_num(info.get("trailingPegRatio") or info.get("pegRatio")),
        price_to_book=_num(info.get("priceToBook")),
        price_to_sales=_num(info.get("priceToSalesTrailing12Months")),
        dividend_yield=_pct(info.get("dividendYield"))
        if _num(info.get("dividendYield")) and _num(info.get("dividendYield")) < 1
        else _num(info.get("dividendYield")),
        profit_margin=_pct(info.get("profitMargins")),
        revenue_growth=_pct(info.get("revenueGrowth")),
        earnings_growth=_pct(info.get("earningsGrowth") or info.get("earningsQuarterlyGrowth")),
        return_on_equity=_pct(info.get("returnOnEquity")),
        target_mean_price=_num(info.get("targetMeanPrice")),
        recommendation=info.get("recommendationKey"),
        fifty_two_week_high=_num(info.get("fiftyTwoWeekHigh")),
        fifty_two_week_low=_num(info.get("fiftyTwoWeekLow")),
        day_change_pct=day_change,
        summary=(info.get("longBusinessSummary") or "").strip(),
    )
    _write_cache(stock)
    return stock


HIST_TTL_SECONDS = 60 * 30  # 30 minutes


def fetch_history(ticker: str, period: str = "6mo", use_cache: bool = True):
    """Daily/weekly closing-price history for a ticker.

    Returns {"dates": [...], "closes": [...]} or None if it can't be fetched.
    Weekly bars for the long ranges keep the point count (and Bollinger math)
    sensible.
    """
    ticker = ticker.upper().strip()
    interval = "1wk" if period in ("2y", "5y") else "1d"
    cache = os.path.join(CACHE_DIR, "hist", f"{ticker}_{period}.json")

    if use_cache and os.path.exists(cache) and time.time() - os.path.getmtime(cache) <= HIST_TTL_SECONDS:
        try:
            with open(cache) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception:
        return None
    if h is None or h.empty or "Close" not in h:
        return None

    dates, closes = [], []
    for ts, close in zip(h.index, h["Close"]):
        c = _num(close)
        if c is not None:
            dates.append(ts.strftime("%Y-%m-%d"))
            closes.append(round(c, 2))
    if len(closes) < 2:
        return None

    out = {"dates": dates, "closes": closes}
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    try:
        with open(cache, "w") as f:
            json.dump(out, f)
    except OSError:
        pass
    return out


def fetch_universe(tickers, use_cache: bool = True, progress=None, max_workers: int = 10):
    """Fetch snapshots for a list of tickers concurrently.

    yfinance calls are network-bound, so pulling them in parallel turns a
    ~60-ticker scan from a minute into a few seconds. Order is preserved and
    tickers that fail to resolve are skipped.
    """
    from concurrent.futures import ThreadPoolExecutor

    tickers = list(tickers)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(lambda t: fetch_stock(t, use_cache=use_cache), tickers))
    return [s for s in results if s is not None]
