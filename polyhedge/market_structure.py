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