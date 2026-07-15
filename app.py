"""Web dashboard for the stock market agent.

Run:  python app.py   then open http://localhost:5000

The home page scans the large-cap universe plus your personal watchlist, scores
every name on Value / Growth / Quality, explains the verdict in plain English,
and lays out your watchlist by triangle tier. You can add or remove tickers from
the search bar. Click any ticker for a full overview.
"""

from __future__ import annotations

import os

from flask import Flask, render_template, abort, request, redirect, url_for, flash

from stock_agent import ai, charts
from stock_agent.data import fetch_stock, fetch_universe, fetch_history
from stock_agent.screener import standouts, score_stocks
from stock_agent.universe import default_universe
from stock_agent import watchlist

app = Flask(__name__)
# Only used to flash "added / removed / not found" messages between requests.
app.secret_key = os.environ.get("STOCK_AGENT_SECRET", "local-dev-secret")


def _scan_tickers():
    """The default large-caps plus everything on the watchlist, de-duplicated."""
    seen, out = set(), []
    for t in default_universe() + watchlist.watchlist_tickers():
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
    for tier_name, tier in watchlist.triangle().items():
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
        tiers=watchlist.TIER_ORDER,
        market_read=read,
        ai_enabled=ai.ai_enabled(),
        count=len(stocks),
    )


@app.route("/watchlist/add", methods=["POST"])
def watchlist_add():
    ticker = (request.form.get("ticker") or "").strip().upper()
    tier = request.form.get("tier") or "Base"
    if not ticker:
        flash("Enter a ticker symbol.", "error")
        return redirect(url_for("home"))
    # Validate against real data before saving, so typos don't clutter the list.
    if fetch_stock(ticker) is None:
        flash(f"Couldn't find '{ticker}' — check the symbol and try again.", "error")
        return redirect(url_for("home"))
    watchlist.add_ticker(tier, ticker)
    flash(f"Added {ticker} to your {tier} tier.", "ok")
    return redirect(url_for("home"))


@app.route("/watchlist/remove", methods=["POST"])
def watchlist_remove():
    ticker = (request.form.get("ticker") or "").strip().upper()
    if ticker:
        watchlist.remove_ticker(ticker)
        flash(f"Removed {ticker} from your watchlist.", "ok")
    return redirect(url_for("home"))


@app.route("/company/<ticker>")
def company(ticker):
    stock = fetch_stock(ticker)
    if stock is None:
        abort(404)
    universe = fetch_universe(_scan_tickers())
    if all(s.ticker != stock.ticker for s in universe):
        universe.append(stock)
    scored = {x.stock.ticker: x for x in score_stocks(universe)}.get(stock.ticker)
    sd = scored.to_dict() if scored else {}
    overview = ai.company_overview(stock)

    # Price chart with Bollinger Bands over the chosen time range.
    rng = request.args.get("range", charts.DEFAULT_RANGE)
    if rng not in charts.RANGE_PERIODS:
        rng = charts.DEFAULT_RANGE
    hist = fetch_history(stock.ticker, rng)
    chart = charts.render(hist["dates"], hist["closes"]) if hist else None

    return render_template(
        "company.html",
        s=stock.to_dict(),
        reasons=sd.get("reasons", []),
        takeaway=sd.get("takeaway"),
        score=sd.get("score"),
        value_score=sd.get("value_score"),
        growth_score=sd.get("growth_score"),
        quality_score=sd.get("quality_score"),
        tier=watchlist.tier_for(stock.ticker),
        overview=overview,
        ai_enabled=ai.ai_enabled(),
        chart=chart,
        ranges=charts.RANGES,
        active_range=rng,
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
