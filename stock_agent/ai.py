"""Claude-powered narrative layer.

Turns the screener's numbers into plain-English reads:
  * `market_read()`      — a short "here's what looks interesting today" summary
  * `company_overview()` — a readable overview of a single company

Everything degrades gracefully: if no Anthropic credentials are configured the
app still works and simply shows the raw data. Generated text is cached to disk
keyed by a hash of its inputs, so we don't pay for the same summary twice.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import List, Optional

MODEL = "claude-opus-4-8"
_AI_CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "ai")


def ai_enabled() -> bool:
    """True when Claude credentials look available (an API key is set)."""
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _client():
    import anthropic

    return anthropic.Anthropic()


def _cache_key(*parts: str) -> str:
    h = hashlib.sha256("||".join(parts).encode()).hexdigest()[:24]
    return os.path.join(_AI_CACHE, f"{h}.txt")


def _read_cache(key: str) -> Optional[str]:
    if os.path.exists(key):
        with open(key) as f:
            return f.read()
    return None


def _write_cache(key: str, text: str) -> None:
    os.makedirs(_AI_CACHE, exist_ok=True)
    with open(key, "w") as f:
        f.write(text)


def _generate(system: str, prompt: str, cache_parts, max_tokens: int = 1200) -> Optional[str]:
    """Run one Claude call, with disk caching. Returns None if AI is unavailable."""
    if not ai_enabled():
        return None

    key = _cache_key(MODEL, system, prompt, *cache_parts)
    cached = _read_cache(key)
    if cached is not None:
        return cached

    try:
        client = _client()
        # Stream so a large max_tokens can't trip an HTTP timeout, then collect
        # the final message. Adaptive thinking lets Claude decide how much to
        # reason about the valuation picture.
        with client.messages.stream(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as e:  # auth error, network, rate limit — never break the page
        return f"__error__:{type(e).__name__}"

    text = "".join(b.text for b in message.content if b.type == "text").strip()
    if text:
        _write_cache(key, text)
    return text


MARKET_SYSTEM = (
    "You are a sober, plain-spoken equity analyst writing for a smart retail "
    "investor. You explain what the valuation data is saying without hype, "
    "hedging appropriately. You never give buy/sell advice or price predictions; "
    "you describe what stands out and why, and note the obvious caveats. Keep it "
    "tight and readable — short paragraphs, no jargon dumps."
)


def market_read(cheap, expensive) -> Optional[str]:
    """A short market-level read over the cheap/expensive standouts.

    `cheap` and `expensive` are lists of ScoredStock.
    """

    def brief(items):
        lines = []
        for x in items:
            s = x.stock
            lines.append(
                f"- {s.ticker} ({s.name}, {s.sector}): "
                f"fwd P/E {s.forward_pe}, P/S {s.price_to_sales}, PEG {s.peg}, "
                f"analyst upside {s.analyst_upside_pct}%, score {x.score:.0f}. "
                f"Signals: {'; '.join(x.reasons) or 'none notable'}"
            )
        return "\n".join(lines) or "(none)"

    prompt = (
        "Below are today's valuation standouts among big US large-caps, scored "
        "against their own sector peers. Write a 3-4 short-paragraph read for a "
        "retail investor: (1) the overall picture, (2) what makes the 'cheap-looking' "
        "names screen cheap and the key caveat for each, (3) what's driving the "
        "'expensive-looking' names, (4) one sentence on what to watch. Be specific "
        "and reference tickers.\n\n"
        f"CHEAP-LOOKING vs peers:\n{brief(cheap)}\n\n"
        f"EXPENSIVE-LOOKING vs peers:\n{brief(expensive)}"
    )
    tickers = ",".join(x.stock.ticker for x in list(cheap) + list(expensive))
    return _generate(MARKET_SYSTEM, prompt, cache_parts=[tickers], max_tokens=1400)


COMPANY_SYSTEM = (
    "You are an equity analyst writing a concise, neutral company overview for a "
    "smart retail investor. Cover: what the business actually does and how it makes "
    "money, where it sits in its industry, and what the valuation and fundamentals "
    "are signalling right now. No buy/sell advice, no price targets of your own. "
    "Plain language, well-structured, roughly 4 short paragraphs."
)


def company_overview(stock) -> Optional[str]:
    """A readable overview of a single company, grounded in its data."""
    s = stock
    facts = (
        f"Ticker: {s.ticker}\nName: {s.name}\nSector: {s.sector}\nIndustry: {s.industry}\n"
        f"Price: {s.price} {s.currency}\nMarket cap: {s.market_cap}\n"
        f"Trailing P/E: {s.trailing_pe}\nForward P/E: {s.forward_pe}\nPEG: {s.peg}\n"
        f"Price/Book: {s.price_to_book}\nPrice/Sales: {s.price_to_sales}\n"
        f"Dividend yield %: {s.dividend_yield}\nProfit margin %: {s.profit_margin}\n"
        f"Revenue growth %: {s.revenue_growth}\n"
        f"Analyst mean target: {s.target_mean_price} (upside {s.analyst_upside_pct}%)\n"
        f"Analyst recommendation: {s.recommendation}\n"
        f"52-week range position: {s.pct_of_52w_range}% of the way from low to high\n"
    )
    summary = s.summary[:2000] if s.summary else "(no company description available)"
    prompt = (
        "Write a company overview using the data below. Ground every claim in the "
        "numbers or the description — do not invent figures. If a data point is "
        "missing, just don't mention it.\n\n"
        f"=== DATA ===\n{facts}\n=== BUSINESS DESCRIPTION ===\n{summary}"
    )
    return _generate(COMPANY_SYSTEM, prompt, cache_parts=[s.ticker], max_tokens=1200)
