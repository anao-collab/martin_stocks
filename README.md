# 📈 Stock Agent

A web dashboard that scans big US large-caps plus your own watchlist, scores
every name on **Value, Growth, and Quality**, and uses **Claude** to explain, in
plain English, what's actually interesting.

Two ideas underneath it:

1. **A stock isn't cheap or expensive in a vacuum.** A utility on 20× earnings
   and a software company on 20× earnings tell completely different stories — so
   value is measured *relative to sector peers*, not on an absolute number.
2. **Cheap isn't the whole story.** A great business that's growing fast can be
   worth a rich price; a cheap one that's shrinking is a trap. So every stock
   gets three sub-scores that blend into one:
   - **Value** — how cheap it looks vs sector peers (forward P/E, price/sales).
   - **Growth** — revenue & earnings growth, analyst upside, and whether earnings
     are expected to rise (forward P/E below trailing).
   - **Quality** — profitability (profit margin, return on equity).

   A profitless fast-grower with no P/E at all can still rank well on Growth +
   Quality — which is the point.

## The app

A TradingView-style layout:

- **Search bar** (top) — look up any ticker and jump straight to its page.
- **Sidebar** (every page) — your watchlist at a glance with quick scores, plus a
  live portfolio summary. Add/remove watchlist tickers right there.
- **Screener** — the main dashboard: most/least interesting names + your triangle.
- **Portfolio** — log what you've bought (ticker, shares, buy price) and see live
  gain/loss. Rows turn red when a holding falls past your −6% sell-rule reminder
  (from class). It's a tracker — nothing places or cancels trades.

## What it does

- **Scans ~50 liquid large-caps** plus your watchlist (data from Yahoo Finance
  via `yfinance` — no API key needed for the data).
- **Ranks the most / least interesting** names by blended score, with the Value /
  Growth / Quality breakdown shown on every card.
- **Lays out your triangle** — your watchlist grouped into Base / Middle / Top
  tiers (see `stock_agent/watchlist.py` to edit it).
- **Writes a plain-English "read"** with Claude Opus 4.8 — what's driving each
  side and the caveats. (Optional; see below.)
- **Company pages** — click any ticker for the full metric set, the sub-score
  breakdown, and an AI-written company overview grounded in the data.

## Quick start

```bash
pip install -r requirements.txt

# Optional but recommended: unlocks the AI reads & overviews.
export ANTHROPIC_API_KEY="sk-ant-..."

python app.py
# open http://localhost:5000
```

Without `ANTHROPIC_API_KEY` the dashboard still works — it just shows the raw
data and the company description instead of the AI narrative.

## How the score works

Each stock gets three sub-scores (higher = better), which blend into a
composite that drives the ranking:

| Sub-score | Built from |
|---|---|
| **Value**   | Forward P/E and price/sales vs the **sector median** |
| **Growth**  | Revenue growth, earnings growth, analyst upside, forward P/E below trailing |
| **Quality** | Profit margin, return on equity |

`composite = Value×0.9 + Growth×0.8 + Quality×0.5`. Missing sub-scores count as
zero, so a name with no P/E still ranks on Growth + Quality. Every contribution
is capped so one wild data point can't dominate. See `stock_agent/screener.py`.

## Your watchlist / triangle

Your tickers are grouped into tiers on the dashboard:

- **Base** (~60%, hold 2–3 yrs), **Middle** (~30%, cyclical AI/robotics/space),
  **Top** (special situations).

**Add or remove tickers right from the page** — use the search bar in the
triangle section (pick a tier, type a symbol, hit Add), and hover any watchlist
card to remove it. Your edits are saved to `user_watchlist.json` (git-ignored,
personal to you) and merged on top of the defaults, so app updates won't wipe
them. The starting defaults live in `stock_agent/watchlist.py`.

## Price charts with Bollinger Bands

Every company page has an interactive price chart:

- **Adjustable time range** — 1M / 3M / 6M / 1Y / 2Y / 5Y buttons.
- **Bollinger Bands** — a 20-period moving average with a ±2σ envelope (a
  volatility gauge, not a buy/sell signal).
- **Hover** anywhere on the chart for the exact date and price.

Charts are rendered server-side as plain SVG — no JavaScript charting library,
no build step, works offline.

## Every card explains itself

Beyond the score, each card carries a one-line **plain-English takeaway** (e.g.
*"looks expensive versus its peers, is growing strongly, and is unprofitable"*)
plus ▲/▼ bullet points spelling out the specific pluses and minuses — so the
"least attractive" names actually say *why*. This works with or without the AI
turned on.

## Project layout

```
app.py                  Flask app (dashboard + company pages)
stock_agent/
  universe.py           the default large-cap ticker list
  watchlist.py          your personal watchlist + triangle tiers
  data.py               yfinance fetching + 30-min disk cache
  screener.py           Value / Growth / Quality scoring
  ai.py                 Claude Opus 4.8 market read + company overviews
templates/              dashboard.html, company.html, base.html
static/style.css        dark dashboard styling
```

## Speed & auto-refresh

- Ticker data is fetched **in parallel**, so a full ~60-name scan takes seconds
  rather than a minute.
- The app keeps an **in-memory snapshot** that a background thread rebuilds every
  10 minutes (`REFRESH_SECONDS`, default 600). Page loads read the snapshot, so
  they're **instant** — only the very first load after startup does the fetch.
- The dashboard shows "Data updated X ago" and **auto-reloads every 10 minutes**
  (only while the tab is visible).

## Notes

- Fetched data and generated AI text are also cached on disk under `.cache/` so
  restarts are warm and you don't pay for the same AI summary twice.
- To force a fresh pull, delete `.cache/`.
- **Informational only — this is not investment advice.** The AI is explicitly
  prompted not to give buy/sell calls or make price predictions.
