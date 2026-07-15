"""Server-side price charts with Bollinger Bands, drawn as plain SVG.

No JavaScript charting library and no build step — the chart is an SVG string
the template drops straight into the page, so it works offline and can't break
from a missing CDN. A small hover script in the template adds a crosshair using
the point data this module also returns.

Bollinger Bands: a moving average (default 20 periods) with an envelope at
±`num_std` standard deviations. When price rides the upper band it's often
called "stretched"; the lower band, "washed out". They're a volatility gauge,
not a buy/sell signal.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

# Selectable time ranges -> the yfinance period string.
RANGES = [
    ("1M", "1mo"),
    ("3M", "3mo"),
    ("6M", "6mo"),
    ("1Y", "1y"),
    ("2Y", "2y"),
    ("5Y", "5y"),
]
RANGE_PERIODS = {p for _, p in RANGES}
DEFAULT_RANGE = "6mo"


def bollinger(closes: List[float], window: int = 20, num_std: float = 2.0):
    """Return (sma, upper, lower) lists aligned to `closes` (None during warmup)."""
    n = len(closes)
    sma: List[Optional[float]] = [None] * n
    upper: List[Optional[float]] = [None] * n
    lower: List[Optional[float]] = [None] * n
    w = min(window, n)  # shrink the window for short series so a band still shows
    for i in range(n):
        if i + 1 >= w:
            window_slice = closes[i + 1 - w:i + 1]
            m = sum(window_slice) / w
            var = sum((x - m) ** 2 for x in window_slice) / w
            sd = var ** 0.5
            sma[i] = m
            upper[i] = m + num_std * sd
            lower[i] = m - num_std * sd
    return sma, upper, lower


def _fmt(v: float) -> str:
    return f"{v:.2f}"


def render(dates: List[str], closes: List[float], width: int = 780, height: int = 340):
    """Build the chart. Returns a dict with the SVG markup and hover points."""
    sma, upper, lower = bollinger(closes)
    n = len(closes)

    left, right, top, bottom = 48, 14, 14, 26
    plot_w = width - left - right
    plot_h = height - top - bottom

    vals = list(closes)
    vals += [v for v in upper if v is not None]
    vals += [v for v in lower if v is not None]
    vmin, vmax = min(vals), max(vals)
    if vmax == vmin:
        vmax += 1  # avoid divide-by-zero on a flat line
    pad = (vmax - vmin) * 0.06
    vmin -= pad
    vmax += pad

    def px(i: int) -> float:
        return left + (plot_w * i / (n - 1) if n > 1 else 0)

    def py(v: float) -> float:
        return top + plot_h * (1 - (v - vmin) / (vmax - vmin))

    # Bollinger band as a filled area (upper across, then lower back).
    band_idx = [i for i in range(n) if upper[i] is not None]
    band = ""
    sma_path = ""
    if band_idx:
        up_pts = " ".join(f"{px(i):.1f},{py(upper[i]):.1f}" for i in band_idx)
        lo_pts = " ".join(f"{px(i):.1f},{py(lower[i]):.1f}" for i in reversed(band_idx))
        band = f'<polygon class="bb-band" points="{up_pts} {lo_pts}" />'
        sma_d = "M" + " L".join(f"{px(i):.1f} {py(sma[i]):.1f}" for i in band_idx)
        sma_path = f'<path class="bb-sma" d="{sma_d}" />'

    # Price line, coloured by whether the period ended up or down.
    up = closes[-1] >= closes[0]
    price_d = "M" + " L".join(f"{px(i):.1f} {py(c):.1f}" for i, c in enumerate(closes))
    price_cls = "price up" if up else "price down"
    price_path = f'<path class="{price_cls}" d="{price_d}" />'

    # Y gridlines + labels (min / mid / max).
    grid = ""
    for frac in (0.0, 0.5, 1.0):
        v = vmin + (vmax - vmin) * frac
        y = py(v)
        grid += f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" />'
        grid += f'<text class="axis" x="{left - 6}" y="{y + 3:.1f}" text-anchor="end">{_fmt(v)}</text>'

    # X date labels: first, middle, last.
    xlabels = ""
    for i in (0, n // 2, n - 1):
        anchor = "start" if i == 0 else ("end" if i == n - 1 else "middle")
        xlabels += f'<text class="axis" x="{px(i):.1f}" y="{height - 8}" text-anchor="{anchor}">{dates[i]}</text>'

    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart-svg" '
        f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        f"{grid}{band}{sma_path}{price_path}{xlabels}"
        f'<line class="crosshair" x1="0" y1="{top}" x2="0" y2="{top + plot_h}" style="display:none" />'
        f'<circle class="cross-dot" r="3.5" style="display:none" />'
        f"</svg>"
    )

    # Points for the hover script (x/y in the 0..width / 0..height viewBox space).
    points = [
        {"x": round(px(i), 1), "y": round(py(closes[i]), 1), "d": dates[i], "p": closes[i]}
        for i in range(n)
    ]

    change_pct = round((closes[-1] / closes[0] - 1) * 100, 2) if closes[0] else None
    return {
        "svg": svg,
        "points": points,
        "width": width,
        "height": height,
        "up": up,
        "change_pct": change_pct,
        "last": closes[-1],
    }
