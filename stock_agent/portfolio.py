"""Your holdings — what you've actually bought.

Each position is a lot: {ticker, shares, cost} where `cost` is the per-share
price you paid. Stored in `positions.json` (git-ignored, personal to you), the
same pattern as the watchlist.

`compute()` values the positions against current prices and flags any that have
fallen past your class sell-rule (the −5–8% stop; we use −6% as the midpoint).
It's a reminder only — nothing here places or cancels any trade.
"""

from __future__ import annotations

import json
import os
from typing import Callable, Optional

ALERT_PCT = -6.0  # flag a position once it's down this much (your ~5-8% sell rule)

_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "positions.json")


def _load() -> dict:
    if os.path.exists(_FILE):
        try:
            with open(_FILE) as f:
                data = json.load(f)
            data.setdefault("positions", [])
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"positions": []}


def _save(data: dict) -> None:
    with open(_FILE, "w") as f:
        json.dump(data, f, indent=2)


def positions() -> list:
    return _load()["positions"]


def add(ticker: str, shares: float, cost: float) -> None:
    data = _load()
    data["positions"].append({
        "ticker": ticker.upper().strip(),
        "shares": float(shares),
        "cost": float(cost),
    })
    _save(data)


def remove(index: int) -> None:
    data = _load()
    if 0 <= index < len(data["positions"]):
        data["positions"].pop(index)
        _save(data)


def compute(price_of: Callable[[str], Optional[float]]) -> dict:
    """Value every position. `price_of(ticker)` returns the current price or None."""
    rows = []
    total_cost = 0.0
    total_val = 0.0
    for i, p in enumerate(positions()):
        shares, cost = p["shares"], p["cost"]
        price = price_of(p["ticker"])
        cost_val = shares * cost
        mkt_val = shares * price if price is not None else None
        gain = (mkt_val - cost_val) if mkt_val is not None else None
        gain_pct = ((price / cost - 1) * 100) if (price is not None and cost) else None
        rows.append({
            "i": i,
            "ticker": p["ticker"],
            "shares": shares,
            "cost": cost,
            "price": price,
            "cost_val": cost_val,
            "mkt_val": mkt_val,
            "gain": gain,
            "gain_pct": round(gain_pct, 1) if gain_pct is not None else None,
            "alert": gain_pct is not None and gain_pct <= ALERT_PCT,
        })
        total_cost += cost_val
        if mkt_val is not None:
            total_val += mkt_val

    total_gain_pct = ((total_val / total_cost - 1) * 100) if total_cost else None
    return {
        "rows": rows,
        "total_cost": total_cost,
        "total_val": total_val,
        "total_gain": total_val - total_cost if rows else 0.0,
        "total_gain_pct": round(total_gain_pct, 1) if total_gain_pct is not None else None,
    }
