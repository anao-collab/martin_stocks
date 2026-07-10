"""Valuation screening.

The core idea: a stock isn't cheap or expensive in a vacuum — it's cheap or
expensive *relative to its sector peers*. A utility on a 20x P/E and a software
company on a 20x P/E are telling very different stories. So we compare each
name's forward P/E and price-to-sales against the median for its sector, then
fold in analyst upside to get a single valuation score.

Positive score  -> looks cheap / undervalued vs peers
Negative score  -> looks expensive / richly valued vs peers
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional

from .data import Stock


@dataclass
class ScoredStock:
    stock: Stock
    score: float
    reasons: List[str]

    def to_dict(self) -> dict:
        d = self.stock.to_dict()
        d["score"] = round(self.score, 1)
        d["reasons"] = self.reasons
        return d


def _sector_medians(stocks: List[Stock]):
    """Median forward P/E and price-to-sales for each sector present."""
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
    """How far below (positive) or above (negative) the peer median a metric sits, in %."""
    if value and median and value > 0 and median > 0:
        return (median - value) / median * 100
    return None


def score_stocks(stocks: List[Stock]) -> List[ScoredStock]:
    """Attach a valuation score and human-readable reasons to each stock."""
    medians = _sector_medians(stocks)
    scored = []

    for s in stocks:
        med = medians.get(s.sector, {})
        reasons: List[str] = []
        score = 0.0

        pe_gap = _gap_pct(s.forward_pe, med.get("forward_pe"))
        if pe_gap is not None:
            # Cap the contribution so one wild number can't dominate.
            score += max(-60, min(60, pe_gap)) * 0.5
            if pe_gap >= 15:
                reasons.append(
                    f"Forward P/E of {s.forward_pe:.1f} is ~{pe_gap:.0f}% below the "
                    f"{s.sector} median"
                )
            elif pe_gap <= -25:
                reasons.append(
                    f"Forward P/E of {s.forward_pe:.1f} is ~{abs(pe_gap):.0f}% above the "
                    f"{s.sector} median"
                )

        ps_gap = _gap_pct(s.price_to_sales, med.get("price_to_sales"))
        if ps_gap is not None:
            score += max(-60, min(60, ps_gap)) * 0.3
            if ps_gap >= 20:
                reasons.append(f"Price/sales sits well below {s.sector} peers")
            elif ps_gap <= -30:
                reasons.append(f"Price/sales is rich versus {s.sector} peers")

        upside = s.analyst_upside_pct
        if upside is not None:
            score += max(-40, min(40, upside)) * 0.6
            if upside >= 15:
                reasons.append(f"Analysts see ~{upside:.0f}% upside to their mean target")
            elif upside <= -5:
                reasons.append(f"Trading ~{abs(upside):.0f}% above the mean analyst target")

        if s.peg is not None and 0 < s.peg < 1:
            score += 8
            reasons.append(f"PEG of {s.peg:.2f} — growth looks cheap relative to earnings")
        elif s.peg is not None and s.peg > 3:
            score -= 6
            reasons.append(f"PEG of {s.peg:.1f} — paying up for the growth")

        # A dividend is a small tilt toward the "value" reading.
        if s.dividend_yield and s.dividend_yield >= 3:
            score += 3
            reasons.append(f"Pays a {s.dividend_yield:.1f}% dividend yield")

        scored.append(ScoredStock(stock=s, score=score, reasons=reasons))

    return scored


def standouts(stocks: List[Stock], n: int = 6):
    """Return the top `n` cheap and top `n` expensive valuation standouts."""
    scored = score_stocks(stocks)
    ranked = sorted(scored, key=lambda x: x.score, reverse=True)
    cheap = [x for x in ranked if x.score > 0][:n]
    expensive = [x for x in reversed(ranked) if x.score < 0][:n]
    return {"cheap": cheap, "expensive": expensive, "all": ranked}
