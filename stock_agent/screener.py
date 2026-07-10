"""Scoring engine: is this a good business, growing, at a fair price?

Every stock gets three sub-scores, each measured so that *higher is better*:

  * Value   — how cheap it looks versus its sector peers (forward P/E, P/S).
  * Growth  — revenue & earnings growth, analyst upside, and whether earnings
              are expected to rise (forward P/E below trailing P/E).
  * Quality — how profitable the business is (profit margin, return on equity).

These blend into one composite score that drives the ranking. A profitless
fast-grower (no P/E at all) can still rank well on Growth + Quality — which is
exactly the point: we're not screening on cheapness alone.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from .data import Stock


@dataclass
class ScoredStock:
    stock: Stock
    score: float                     # composite
    value_score: Optional[float]
    growth_score: Optional[float]
    quality_score: Optional[float]
    reasons: List[str]

    def to_dict(self) -> dict:
        d = self.stock.to_dict()
        d["score"] = round(self.score, 1)
        d["value_score"] = round(self.value_score) if self.value_score is not None else None
        d["growth_score"] = round(self.growth_score) if self.growth_score is not None else None
        d["quality_score"] = round(self.quality_score) if self.quality_score is not None else None
        d["reasons"] = self.reasons
        return d


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class _Accumulator:
    """Adds up weighted contributions and remembers whether any data was present."""

    def __init__(self):
        self.total = 0.0
        self.count = 0

    def add(self, value: Optional[float], weight: float, lo: float, hi: float):
        if value is not None:
            self.total += _clamp(value, lo, hi) * weight
            self.count += 1

    def result(self, lo: float, hi: float) -> Optional[float]:
        if self.count == 0:
            return None
        return _clamp(self.total, lo, hi)


def _sector_medians(stocks: List[Stock]):
    by_sector = {}
    for s in stocks:
        by_sector.setdefault(s.sector, []).append(s)
    medians = {}
    for sector, group in by_sector.items():
        pes = [s.forward_pe for s in group if s.forward_pe and s.forward_pe > 0]
        pss = [s.price_to_sales for s in group if s.price_to_sales and s.price_to_sales > 0]
        medians[sector] = {
            "forward_pe": statistics.median(pes) if pes else None,
            "price_to_sales": statistics.median(pss) if pss else None,
        }
    return medians


def _gap_pct(value: Optional[float], median: Optional[float]) -> Optional[float]:
    """% below (positive) or above (negative) the peer median."""
    if value and median and value > 0 and median > 0:
        return (median - value) / median * 100
    return None


def _score_one(s: Stock, med: dict):
    reasons: List[str] = []

    # ---- Value: cheap versus sector peers ----------------------------------
    value = _Accumulator()
    pe_gap = _gap_pct(s.forward_pe, med.get("forward_pe"))
    value.add(pe_gap, 0.6, -50, 50)
    ps_gap = _gap_pct(s.price_to_sales, med.get("price_to_sales"))
    value.add(ps_gap, 0.4, -50, 50)
    value_score = value.result(-50, 50)

    if pe_gap is not None and pe_gap >= 15:
        reasons.append(f"Forward P/E of {s.forward_pe:.1f} is ~{pe_gap:.0f}% below {s.sector} peers")
    elif pe_gap is not None and pe_gap <= -25:
        reasons.append(f"Forward P/E of {s.forward_pe:.1f} is ~{abs(pe_gap):.0f}% above {s.sector} peers")

    # ---- Growth: is it actually growing? -----------------------------------
    growth = _Accumulator()
    growth.add(s.revenue_growth, 1.0, -25, 50)
    growth.add(s.earnings_growth, 0.5, -40, 60)
    growth.add(s.analyst_upside_pct, 0.7, -25, 40)
    earnings_rising = (
        s.forward_pe and s.trailing_pe and 0 < s.forward_pe < s.trailing_pe
    )
    if earnings_rising:
        growth.add(8.0, 1.0, 0, 8)  # forward P/E below trailing => earnings expected up
    growth_score = growth.result(-80, 95)

    if s.revenue_growth is not None and s.revenue_growth >= 20:
        reasons.append(f"Revenue growing ~{s.revenue_growth:.0f}% year-over-year")
    if s.earnings_growth is not None and s.earnings_growth >= 25:
        reasons.append(f"Earnings up ~{s.earnings_growth:.0f}% year-over-year")
    if s.analyst_upside_pct is not None and s.analyst_upside_pct >= 15:
        reasons.append(f"Analysts see ~{s.analyst_upside_pct:.0f}% upside to their mean target")
    if earnings_rising:
        reasons.append("Earnings expected to rise (forward P/E sits below trailing)")
    if s.revenue_growth is not None and s.revenue_growth <= -10:
        reasons.append(f"Revenue shrinking (~{s.revenue_growth:.0f}% year-over-year)")

    # ---- Quality: is the business any good? --------------------------------
    quality = _Accumulator()
    quality.add(s.profit_margin, 0.7, -25, 45)
    quality.add(s.return_on_equity, 0.4, -20, 50)
    quality_score = quality.result(-40, 60)

    if s.profit_margin is not None and s.profit_margin >= 20:
        reasons.append(f"High profit margin (~{s.profit_margin:.0f}%)")
    elif s.profit_margin is not None and s.profit_margin < 0:
        reasons.append("Not yet profitable (negative margin)")
    if s.return_on_equity is not None and s.return_on_equity >= 20:
        reasons.append(f"Strong return on equity (~{s.return_on_equity:.0f}%)")

    if s.dividend_yield and s.dividend_yield >= 3:
        reasons.append(f"Pays a {s.dividend_yield:.1f}% dividend")

    # ---- Blend. Missing sub-scores count as 0 so the others still speak. ----
    composite = (
        (value_score or 0) * 0.9
        + (growth_score or 0) * 0.8
        + (quality_score or 0) * 0.5
    )

    return ScoredStock(
        stock=s,
        score=composite,
        value_score=value_score,
        growth_score=growth_score,
        quality_score=quality_score,
        reasons=reasons,
    )


def score_stocks(stocks: List[Stock]) -> List[ScoredStock]:
    medians = _sector_medians(stocks)
    return [_score_one(s, medians.get(s.sector, {})) for s in stocks]


def standouts(stocks: List[Stock], n: int = 6):
    """Top `n` most attractive and `n` least attractive names by composite score."""
    scored = score_stocks(stocks)
    ranked = sorted(scored, key=lambda x: x.score, reverse=True)
    top = [x for x in ranked if x.score > 0][:n]
    bottom = [x for x in reversed(ranked) if x.score < 0][:n]
    return {"top": top, "bottom": bottom, "all": ranked}
