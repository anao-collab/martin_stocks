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

`stock_agent/watchlist.py` holds your tickers grouped into tiers:

- **Base** (~60%, hold 2–3 yrs), **Middle** (~30%, cyclical AI/robotics/space),
  **Top** (special situations).

Edit that file to change what you track — the tickers are scanned automatically
and shown grouped by tier on the dashboard.

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

## Notes

- Fetched data and generated AI text are cached under `.cache/` (30 min for
  market data) so reloads are fast and you don't pay for the same summary twice.
- To force a fresh data pull, set `STOCK_AGENT_REFRESH=1` or delete `.cache/`.
- **Informational only — this is not investment advice.** The AI is explicitly
  prompted not to give buy/sell calls or make price predictions.
