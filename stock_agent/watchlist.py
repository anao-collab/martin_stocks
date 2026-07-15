"""Your personal watchlist, organised as the 'triangle' from class.

    Base   (~60%) — foundation holds, 2-3 years
    Middle (~30%) — cyclical AI / robotics / space, 3-12 months
    Top           — special situations, short-lived

DEFAULTS below are the starting point. Anything you add or remove from the
dashboard's search bar is saved to `user_watchlist.json` (git-ignored, personal
to you) and merged on top of the defaults — so the app updating won't wipe your
changes, and your list won't get committed to the repo.

Note: SpaceX is private and not tradable, so it can't be included here.
"""

from __future__ import annotations

import json
import os

TIER_ORDER = ["Base", "Middle", "Top"]

TIER_BLURBS = {
    "Base": "~60% · foundation · hold 2-3 years",
    "Middle": "~30% · cyclical AI / robotics / space · hold 3-12 months",
    "Top": "special situations · short-lived",
}

DEFAULTS = {
    "Base": ["GOOG", "MU", "AMZN", "NVDA"],
    "Middle": ["IREN", "NBIS", "MRVL", "JOBY", "RKLB", "FSLR", "LITE", "COHR", "CRS", "PL"],
    "Top": ["LULU", "NKE"],
}

_USER_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_watchlist.json")


def _load_user() -> dict:
    """User edits: {"added": {tier: [...]}, "removed": [...]}. Tolerant of a missing/bad file."""
    if os.path.exists(_USER_FILE):
        try:
            with open(_USER_FILE) as f:
                data = json.load(f)
            data.setdefault("added", {})
            data.setdefault("removed", [])
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"added": {}, "removed": []}


def _save_user(data: dict) -> None:
    with open(_USER_FILE, "w") as f:
        json.dump(data, f, indent=2)


def triangle():
    """The effective triangle: defaults + your additions, minus your removals."""
    user = _load_user()
    removed = {t.upper() for t in user.get("removed", [])}
    out = {}
    for tier in TIER_ORDER:
        combined, seen = [], set()
        for t in DEFAULTS.get(tier, []) + user.get("added", {}).get(tier, []):
            u = t.upper()
            if u not in seen and u not in removed:
                seen.add(u)
                combined.append(u)
        out[tier] = {"blurb": TIER_BLURBS[tier], "tickers": combined}
    return out


def watchlist_tickers():
    """Every ticker across all tiers, de-duplicated, order preserved."""
    seen, out = set(), []
    for tier in triangle().values():
        for t in tier["tickers"]:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def tier_for(ticker: str):
    ticker = ticker.upper()
    for name, tier in triangle().items():
        if ticker in tier["tickers"]:
            return name
    return None


def add_ticker(tier: str, ticker: str) -> bool:
    """Add a ticker to a tier. Returns False if the tier name is invalid."""
    tier = tier.capitalize()
    if tier not in TIER_ORDER:
        return False
    ticker = ticker.upper().strip()
    if not ticker:
        return False
    user = _load_user()
    # If it was previously removed, un-remove it.
    user["removed"] = [t for t in user.get("removed", []) if t.upper() != ticker]
    added = user.setdefault("added", {}).setdefault(tier, [])
    # Remove from any other tier's additions so it lives in one place.
    for other in user["added"]:
        user["added"][other] = [t for t in user["added"][other] if t.upper() != ticker]
    user["added"].setdefault(tier, [])
    if ticker not in (t.upper() for t in user["added"][tier]):
        user["added"][tier].append(ticker)
    _save_user(user)
    return True


def remove_ticker(ticker: str) -> None:
    """Remove a ticker from the watchlist entirely (works for defaults too)."""
    ticker = ticker.upper().strip()
    user = _load_user()
    for tier in user.get("added", {}):
        user["added"][tier] = [t for t in user["added"][tier] if t.upper() != ticker]
    if ticker not in (t.upper() for t in user.get("removed", [])):
        user.setdefault("removed", []).append(ticker)
    _save_user(user)
