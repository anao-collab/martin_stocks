"""Web dashboard for the stock market agent.

Run:  python app.py   then open http://localhost:5000

The home page scans the large-cap universe, ranks valuation standouts, and (if
Claude credentials are set) shows an AI market read. Click any ticker for a full
company overview.
"""

from __future__ import annotations

import os

from flask import Flask, render_template, abort

from stock_agent import ai
from stock_agent.data import fetch_stock, fetch_universe
from stock_agent.screener import standouts, score_stocks
from stock_agent.universe import default_universe

app = Flask(__name__)


def _scan(refresh: bool = False):
    stocks = fetch_universe(default_universe(), use_cache=not refresh)
    result = standouts(stocks, n=6)
    return stocks, result


@app.route("/")
def home():
    refresh = os.environ.get("STOCK_AGENT_REFRESH") == "1"
    stocks, result = _scan(refresh=refresh)
    read = ai.market_read(result["cheap"], result["expensive"])
    return render_template(
        "dashboard.html",
        cheap=[x.to_dict() for x in result["cheap"]],
        expensive=[x.to_dict() for x in result["expensive"]],
        market_read=read,
        ai_enabled=ai.ai_enabled(),
        count=len(stocks),
    )


@app.route("/company/<ticker>")
def company(ticker):
    stock = fetch_stock(ticker)
    if stock is None:
        abort(404)
    # Score it within the full universe so the sector context is meaningful.
    universe = fetch_universe(default_universe())
    if all(s.ticker != stock.ticker for s in universe):
        universe.append(stock)
    scored = {x.stock.ticker: x for x in score_stocks(universe)}.get(stock.ticker)
    overview = ai.company_overview(stock)
    return render_template(
        "company.html",
        s=stock.to_dict(),
        reasons=scored.reasons if scored else [],
        score=round(scored.score, 1) if scored else None,
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
