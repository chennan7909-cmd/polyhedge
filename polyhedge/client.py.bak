"""
Polymarket data client.

Read-only access only — no wallet, no auth, no trade submission.
- Gamma API  (https://gamma-api.polymarket.com): market discovery + prices. PUBLIC.
- CLOB API   (https://clob.polymarket.com): order book depth for slippage estimates. PUBLIC (read).

Verified May 2026: Gamma is fully public (~60 req/min). `outcomePrices` gives the
current YES/NO implied probabilities. `clobTokenIds` maps each outcome to a CLOB
token id you can look up in /order-book.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


@dataclass
class Market:
    id: str
    question: str
    slug: str
    outcomes: list[str]                 # e.g. ["Yes", "No"]
    prices: list[float]                 # aligned with outcomes; implied probabilities
    token_ids: list[str]                # CLOB token id per outcome
    volume: float = 0.0
    liquidity: float = 0.0
    end_date: str | None = None
    neg_risk: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def yes_price(self) -> float | None:
        for o, p in zip(self.outcomes, self.prices):
            if o.lower() in ("yes", "true"):
                return p
        return self.prices[0] if self.prices else None


def _parse_market(m: dict[str, Any]) -> Market:
    # Gamma returns several fields as JSON-encoded strings.
    def _arr(v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []
        return v or []

    outcomes = _arr(m.get("outcomes"))
    prices = [float(x) for x in _arr(m.get("outcomePrices"))]
    token_ids = _arr(m.get("clobTokenIds"))
    return Market(
        id=str(m.get("id")),
        question=m.get("question", ""),
        slug=m.get("slug", ""),
        outcomes=outcomes,
        prices=prices,
        token_ids=token_ids,
        volume=float(m.get("volume") or 0),
        liquidity=float(m.get("liquidity") or 0),
        end_date=m.get("endDate"),
        neg_risk=bool(m.get("negRisk", False)),
        raw=m,
    )


class PolymarketClient:
    def __init__(self, timeout: float = 15.0):
        self._http = httpx.Client(timeout=timeout, headers={"User-Agent": "polyhedge/0.1"})

    def list_markets(self, limit: int = 20, search: str | None = None) -> list[Market]:
        params: dict[str, Any] = {"closed": "false", "limit": limit,
                                  "order": "volume", "ascending": "false"}
        r = self._http.get(f"{GAMMA}/markets", params=params)
        r.raise_for_status()
        markets = [_parse_market(x) for x in r.json()]
        if search:
            s = search.lower()
            markets = [m for m in markets if s in m.question.lower()]
        return markets

    def get_market(self, market_id: str) -> Market:
        r = self._http.get(f"{GAMMA}/markets/{market_id}")
        r.raise_for_status()
        return _parse_market(r.json())

    def search(self, query: str, limit: int = 50) -> list[Market]:
        """Pull a wider list then filter client-side (Gamma search is fuzzy)."""
        return self.list_markets(limit=limit, search=query)

    def order_book(self, token_id: str) -> dict[str, Any]:
        """Live book for one outcome token. Used to estimate fill slippage."""
        r = self._http.get(f"{CLOB}/order-book", params={"token_id": token_id})
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self._http.close()
