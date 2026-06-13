"""Parse a Market into structured fields for hedge-compatibility checks.

Two markets only offset each other if they share the same underlying asset,
time window, payoff direction, and settlement style. A "touch any time in
June" market and an "above X on June 30" market mention the same number but
settle on different conditions -- hedging one with the other is basis risk.
This module extracts the fields needed to detect that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from .client import Market


class Settlement(str, Enum):
    TOUCH = "touch"
    AT_EXPIRY = "at_expiry"
    UNKNOWN = "unknown"


class Direction(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    UNKNOWN = "unknown"


class Relationship(str, Enum):
    SAME_MARKET = "same_market"
    COMPATIBLE_CROSS_MARKET = "compatible_cross"
    RELATED_NOT_HEDGE = "related_not_hedge"
    REJECTED = "rejected"


_ASSETS = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth"),
    "SOL": ("solana", "sol"),
}

_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")


@dataclass
class MarketStructure:
    market: Market
    asset: str | None
    threshold: float | None
    direction: Direction
    settlement: Settlement
    window: str | None

    @property
    def question(self) -> str:
        return self.market.question


def _find_asset(t: str) -> str | None:
    for sym, names in _ASSETS.items():
        for n in names:
            if re.search(rf"\b{n}\b", t):
                return sym
    return None


def _find_threshold(text: str) -> float | None:
    m = re.search(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,6})", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _find_specific_day(t: str) -> str | None:
    m = re.search(rf"\b({'|'.join(_MONTHS)})\s+([0-9]{{1,2}})\b", t)
    if m:
        return f"{m.group(1)} {int(m.group(2))}"
    return None


def _find_month(t: str) -> str | None:
    for mo in _MONTHS:
        if re.search(rf"\b{mo}\b", t):
            return mo
    return None


def parse_market(market: Market) -> MarketStructure:
    t = market.question.lower()

    asset = _find_asset(t)
    threshold = _find_threshold(t)

    if any(w in t for w in ("dip to", "drop to", "fall to", "crash to",
                            "dip below", "fall below", "below", "under")):
        direction = Direction.BELOW
    elif any(w in t for w in ("reach", "hit", "touch", "above", "over", "exceed")):
        direction = Direction.ABOVE
    else:
        direction = Direction.UNKNOWN

    specific_day = _find_specific_day(t)
    if specific_day is not None:
        settlement = Settlement.AT_EXPIRY
        window = specific_day
    elif any(w in t for w in ("reach", "hit", "dip", "drop", "fall", "touch", "crash")):
        settlement = Settlement.TOUCH
        window = _find_month(t)
    else:
        settlement = Settlement.UNKNOWN
        window = _find_month(t)

    return MarketStructure(
        market=market, asset=asset, threshold=threshold,
        direction=direction, settlement=settlement, window=window,
    )


def classify_relationship(position: MarketStructure,
                          candidate: MarketStructure) -> tuple[Relationship, str]:
    """Decide whether `candidate` can hedge `position`, and why.

    Four-dimension check: same asset, compatible settlement, same time window,
    and opposite payoff direction. Settlement is checked before the window
    label because a touch-vs-expiry mismatch is the more fundamental basis risk.
    """
    p, c = position, candidate

    if p.market.id == c.market.id:
        return Relationship.SAME_MARKET, "same market, opposite side: exact binary hedge"

    if p.asset is None or c.asset is None or p.asset != c.asset:
        return Relationship.REJECTED, f"asset mismatch: {p.asset} vs {c.asset}"

    if p.threshold is None or c.threshold is None:
        return Relationship.REJECTED, "threshold unparseable on one side"
    if Direction.UNKNOWN in (p.direction, c.direction):
        return Relationship.REJECTED, "direction unparseable on one side"
    if Settlement.UNKNOWN in (p.settlement, c.settlement):
        return Relationship.REJECTED, "settlement unparseable on one side"

    if p.settlement != c.settlement:
        return (Relationship.REJECTED,
                f"settlement mismatch ({p.settlement.value} vs {c.settlement.value}): "
                "this is basis risk -- the markets resolve on different conditions")

    p_src = (p.market.raw or {}).get("resolution_source")
    c_src = (c.market.raw or {}).get("resolution_source")
    if p_src and c_src and p_src != c_src:
        return (Relationship.REJECTED,
                f"resolution-source mismatch ({p_src} vs {c_src}): basis risk -- "
                "the same price can trigger at different moments across venues, "
                "and USD vs USDT diverge if the peg breaks")

    if p.window and c.window and p.window != c.window:
        return Relationship.REJECTED, f"time-window mismatch: {p.window} vs {c.window}"

    if p.direction == c.direction:
        return (Relationship.RELATED_NOT_HEDGE,
                "same payoff direction: correlated exposure, not an offsetting hedge")

    return (Relationship.COMPATIBLE_CROSS_MARKET,
            "opposite direction with matching asset, window, and settlement")
