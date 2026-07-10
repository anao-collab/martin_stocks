# 📈 Stock Agent

A web dashboard that scans big US large-caps, flags the **valuation standouts**
— names that look cheap or expensive versus their own sector peers — and uses
**Claude** to explain, in plain English, what's actually interesting.

Built around one idea: a stock isn't cheap or expensive in a vacuum. A utility
on 20× earnings and a software company on 20× earnings are telling completely
different stories. So every name is scored **relative to its sector**, not on an
absolute number.

## What it does

- **Scans ~50 liquid large-caps** across every major sector (data from Yahoo
  Finance via `yfinance` — no API key needed for the data).
- **Ranks valuation standouts** on forward P/E and price-to-sales versus the
  sector median, plus PEG and analyst upside. Positive score → looks cheap;
  negative → looks expensive.
- **Writes a plain-English "read"** with Claude Opus 4.8 — the overall picture,
  what's driving each side, and the caveats. (Optional; see below.)
- **Company pages** — click any ticker for the full metric set and an AI-written
  company overview grounded in the data.

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

For each stock, within its sector:

| Signal | Contribution |
|---|---|
| Forward P/E below sector median | + (cheap) |
| Price/Sales below sector median | + (cheap) |
| Analyst upside to mean target | + / − |
| PEG < 1 | small + · PEG > 3 | small − |
| Dividend yield ≥ 3% | small + |

Scores are capped per-signal so one wild data point can't dominate. See
`stock_agent/screener.py`.

## Project layout

```
app.py                  Flask app (dashboard + company pages)
stock_agent/
  universe.py           the large-cap ticker list
  data.py               yfinance fetching + 30-min disk cache
  screener.py           sector-relative valuation scoring
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
