"""Web dashboard for the stock market agent.

Run:  python app.py   then open http://localhost:5000

The home page scans the large-cap universe plus your personal watchlist, scores
every name on Value / Growth / Quality, shows the strongest and weakest, and
lays out your watchlist by triangle tier. Click any ticker for a full overview.
"""

from __future__ import annotations

import os

from flask import Flask, render_template, abort

from stock_agent import ai
from stock_agent.data import fetch_stock, fetch_universe
from stock_agent.screener import standouts, score_stocks
from stock_agent.universe import default_universe
from stock_agent.watchlist import TRIANGLE, watchlist_tickers, tier_for

app = Flask(__name__)


def _scan_tickers():
    """The default large-caps plus everything on the watchlist, de-duplicated."""
    seen, out = set(), []
    for t in default_universe() + watchlist_tickers():
        u = t.upper()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _scan(refresh: bool = False):
    stocks = fetch_universe(_scan_tickers(), use_cache=not refresh)
    scored = {x.stock.ticker: x for x in score_stocks(stocks)}
    result = standouts(stocks, n=6)
    return stocks, scored, result


def _triangle_view(scored):
    """Group the watchlist into its tiers, each sorted by composite score."""
    view = []
    for tier_name, tier in TRIANGLE.items():
        rows = [scored[t] for t in tier["tickers"] if t in scored]
        rows.sort(key=lambda x: x.score, reverse=True)
        view.append({
            "name": tier_name,
            "blurb": tier["blurb"],
            "stocks": [x.to_dict() for x in rows],
            "missing": [t for t in tier["tickers"] if t not in scored],
        })
    return view


@app.route("/")
def home():
    refresh = os.environ.get("STOCK_AGENT_REFRESH") == "1"
    stocks, scored, result = _scan(refresh=refresh)
    read = ai.market_read(result["top"], result["bottom"])
    return render_template(
        "dashboard.html",
        top=[x.to_dict() for x in result["top"]],
        bottom=[x.to_dict() for x in result["bottom"]],
        triangle=_triangle_view(scored),
        market_read=read,
        ai_enabled=ai.ai_enabled(),
        count=len(stocks),
    )


@app.route("/company/<ticker>")
def company(ticker):
    stock = fetch_stock(ticker)
    if stock is None:
        abort(404)
    # Score within the full scanned set so sector context is meaningful.
    universe = fetch_universe(_scan_tickers())
    if all(s.ticker != stock.ticker for s in universe):
        universe.append(stock)
    scored = {x.stock.ticker: x for x in score_stocks(universe)}.get(stock.ticker)
    overview = ai.company_overview(stock)
    return render_template(
        "company.html",
        s=stock.to_dict(),
        reasons=scored.reasons if scored else [],
        score=round(scored.score, 1) if scored else None,
        value_score=scored.to_dict()["value_score"] if scored else None,
        growth_score=scored.to_dict()["growth_score"] if scored else None,
        quality_score=scored.to_dict()["quality_score"] if scored else None,
        tier=tier_for(stock.ticker),
        overview=overview,
        ai_enabled=ai.ai_enabled(),
    )


@app.template_filter("money")
def money(value):
    """Format a market cap into $1.2T / $340B / $4.5B."""
    if value is None:
        return "—"
    for unit, size in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if abs(value) >= size:
            return f"${value / size:.1f}{unit}"
    return f"${value:,.0f}"


@app.template_filter("num")
def num(value, digits=1):
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "—"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
