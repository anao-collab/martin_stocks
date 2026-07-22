"""Web dashboard for the stock market agent.

Run:  python app.py   then open http://localhost:5000

The home page scans the large-cap universe plus your personal watchlist, scores
every name on Value / Growth / Quality, explains the verdict in plain English,
and lays out your watchlist by triangle tier. You can add or remove tickers from
the search bar. Click any ticker for a full overview.
"""

from __future__ import annotations

import os

import hmac
import threading
import time

from flask import Flask, render_template, abort, request, redirect, url_for, flash, Response

from stock_agent import ai, charts, portfolio
from stock_agent.data import fetch_stock, fetch_universe, fetch_history
from stock_agent.screener import standouts, score_stocks
from stock_agent.universe import default_universe
from stock_agent import watchlist

app = Flask(__name__)
# Only used to flash "added / removed / not found" messages between requests.
app.secret_key = os.environ.get("STOCK_AGENT_SECRET", "local-dev-secret")

# Optional password gate. When APP_PASSWORD is set (e.g. on the deployed site),
# every page requires it. Left unset locally, so it's open on your own machine.
APP_USERNAME = os.environ.get("APP_USERNAME", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")


@app.before_request
def _require_login():
    if not APP_PASSWORD:
        return  # no password configured — open (local dev)
    auth = request.authorization
    if auth and auth.username == APP_USERNAME and hmac.compare_digest(auth.password or "", APP_PASSWORD):
        return
    return Response(
        "Login required.", 401, {"WWW-Authenticate": 'Basic realm="Stock Agent"'}
    )


REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "600"))  # 10 minutes


def _scan_tickers():
    """The default large-caps plus everything on the watchlist, de-duplicated."""
    seen, out = set(), []
    for t in default_universe() + watchlist.watchlist_tickers():
        u = t.upper()
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


# ---- In-memory snapshot, refreshed on a background timer ------------------
# Requests read this snapshot (instant) instead of fetching ~60 tickers inline.
# A daemon thread rebuilds it every REFRESH_SECONDS with fresh data.
_snapshot = {"stocks": [], "scored": {}, "result": {"top": [], "bottom": []}, "ts": 0.0}
_snap_lock = threading.Lock()
_started = False
_start_lock = threading.Lock()


def _rebuild(refresh: bool):
    stocks = fetch_universe(_scan_tickers(), use_cache=not refresh)
    scored = {x.stock.ticker: x for x in score_stocks(stocks)}
    result = standouts(stocks, n=6)
    with _snap_lock:
        _snapshot.update(stocks=stocks, scored=scored, result=result, ts=time.time())


def _refresh_loop():
    while True:
        time.sleep(REFRESH_SECONDS)
        try:
            _rebuild(refresh=True)
        except Exception:
            pass  # a bad fetch shouldn't kill the refresher


def _ensure_started():
    """Build the first snapshot and start the background refresher, once."""
    global _started
    with _start_lock:
        if _started:
            return
        _started = True
        _rebuild(refresh=False)  # synchronous first build (parallel, a few seconds)
        threading.Thread(target=_refresh_loop, daemon=True).start()


def _get_snapshot():
    _ensure_started()
    with _snap_lock:
        return dict(_snapshot)


def _price(ticker: str):
    """Current price for a ticker — from the warm snapshot if scanned, else fetched."""
    x = _get_snapshot()["scored"].get(ticker.upper())
    if x:
        return x.stock.price
    s = fetch_stock(ticker)
    return s.price if s else None


@app.context_processor
def _inject_sidebar():
    """Watchlist + portfolio summary for the sidebar, available on every page."""
    scored = _get_snapshot()["scored"]
    tiers = []
    for name, tier in watchlist.triangle().items():
        rows = [scored[t].to_dict() for t in tier["tickers"] if t in scored]
        tiers.append({"name": name, "stocks": rows})
    return {
        "sidebar_tiers": tiers,
        "portfolio_summary": portfolio.compute(_price),
        "tiers": watchlist.TIER_ORDER,
    }


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


def _ago(ts: float) -> str:
    if not ts:
        return "just now"
    minutes = int((time.time() - ts) // 60)
    if minutes <= 0:
        return "just now"
    return "1 minute ago" if minutes == 1 else f"{minutes} minutes ago"


@app.route("/")
def home():
    snap = _get_snapshot()
    result, scored, stocks = snap["result"], snap["scored"], snap["stocks"]
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
        updated_ago=_ago(snap["ts"]),
        refresh_seconds=REFRESH_SECONDS,
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
    _rebuild(refresh=False)  # so the new ticker shows up immediately
    flash(f"Added {ticker} to your {tier} tier.", "ok")
    return redirect(url_for("home"))


@app.route("/watchlist/remove", methods=["POST"])
def watchlist_remove():
    ticker = (request.form.get("ticker") or "").strip().upper()
    if ticker:
        watchlist.remove_ticker(ticker)
        _rebuild(refresh=False)
        flash(f"Removed {ticker} from your watchlist.", "ok")
    return redirect(url_for("home"))


@app.route("/lookup")
def lookup():
    """Global search: resolve a ticker and jump to its company page."""
    q = (request.args.get("q") or "").strip().upper()
    if not q:
        return redirect(url_for("home"))
    if fetch_stock(q) is None:
        flash(f"Couldn't find '{q}'. Check the symbol and try again.", "error")
        return redirect(request.referrer or url_for("home"))
    return redirect(url_for("company", ticker=q))


@app.route("/portfolio")
def portfolio_page():
    return render_template(
        "portfolio.html",
        port=portfolio.compute(_price),
        alert_pct=portfolio.ALERT_PCT,
    )


@app.route("/portfolio/add", methods=["POST"])
def portfolio_add():
    ticker = (request.form.get("ticker") or "").strip().upper()
    try:
        shares = float(request.form.get("shares") or 0)
        cost = float(request.form.get("cost") or 0)
    except ValueError:
        flash("Enter valid numbers for shares and buy price.", "error")
        return redirect(url_for("portfolio_page"))
    if not ticker or shares <= 0 or cost <= 0:
        flash("Enter a ticker, a share count, and a buy price.", "error")
        return redirect(url_for("portfolio_page"))
    if fetch_stock(ticker) is None:
        flash(f"Couldn't find '{ticker}'.", "error")
        return redirect(url_for("portfolio_page"))
    portfolio.add(ticker, shares, cost)
    flash(f"Added {shares:g} shares of {ticker}.", "ok")
    return redirect(url_for("portfolio_page"))


@app.route("/portfolio/remove", methods=["POST"])
def portfolio_remove():
    try:
        idx = int(request.form.get("index"))
    except (TypeError, ValueError):
        idx = -1
    portfolio.remove(idx)
    flash("Removed holding.", "ok")
    return redirect(url_for("portfolio_page"))


@app.route("/company/<ticker>")
def company(ticker):
    snap = _get_snapshot()
    stock = fetch_stock(ticker)  # single ticker, served from the warm disk cache
    if stock is None:
        abort(404)
    # Reuse the already-scored snapshot for sector context; only re-score if this
    # ticker wasn't part of the scan.
    scored = snap["scored"].get(stock.ticker)
    if scored is None:
        universe = snap["stocks"] + [stock]
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
