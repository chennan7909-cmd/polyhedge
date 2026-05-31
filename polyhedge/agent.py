"""
The Agent layer.

Single-agent, tool-calling design (no CrewAI). In 48 hours a single agent with
3 clean tools is far more reliable on stage than multi-agent message passing.

Flow:
  user: "I'm worried my YES position on <event> loses"
    -> agent calls find_market(query)
    -> agent calls get_prices(market_id)   [reads opposite-outcome ask]
    -> agent calls compute_hedge(...)
    -> agent returns the plan + risk narrative

This module degrades gracefully: if no ANTHROPIC_API_KEY is set, `plan_hedge`
runs the deterministic pipeline directly (great for a reliable live demo), and
the LLM is only used to phrase the final advice.
"""
from __future__ import annotations

import os
from dataclasses import asdict

from .client import PolymarketClient, Market
from .hedge import Position, Side, Intent, compute_hedge, narrate


def _opposite_ask(market: Market, side: Side) -> float:
    """Current price to BUY the hedge outcome. Fallback to outcomePrices if no book."""
    target = "no" if side == Side.YES else "yes"
    for o, p in zip(market.outcomes, market.prices):
        if o.lower().startswith(target):
            return p
    # last resort: complement of the position-side price
    return 1 - (market.yes_price or 0.5)


def plan_hedge(
    query: str,
    side: Side,
    shares: float,
    avg_price: float,
    intent: Intent = Intent.BREAK_EVEN_ON_LOSS,
    floor: float = 0.0,
    client: PolymarketClient | None = None,
) -> dict:
    """Deterministic core the agent calls. Returns a JSON-able plan."""
    owns_client = client is None
    client = client or PolymarketClient()
    try:
        matches = client.search(query, limit=50)
        if not matches:
            return {"error": f"No open market matched '{query}'."}
        market = matches[0]
        hedge_price = _opposite_ask(market, side)
        pos = Position(side=side, shares=shares, avg_price=avg_price)
        plan = compute_hedge(pos, hedge_price, intent=intent, floor=floor)
        return {
            "market": {"id": market.id, "question": market.question,
                       "volume": market.volume, "prices": dict(zip(market.outcomes, market.prices))},
            "position": asdict(pos) | {"side": pos.side.value},
            "plan": asdict(plan) | {"hedge_side": plan.hedge_side.value,
                                    "intent": plan.intent.value},
            "narrative": narrate(pos, plan),
        }
    finally:
        if owns_client:
            client.close()


# ---- Optional LLM wrapper (Claude tool-calling). Falls back cleanly. --------

SYSTEM = (
    "You are a risk officer for prediction-market positions. Use the provided "
    "hedge plan numbers EXACTLY — never invent prices or share counts. Explain "
    "the trade-off between downside protection and upside given up in 3-4 sentences. "
    "If the plan note warns the hedge locks a loss, say so plainly."
)


def advise(query: str, side: Side, shares: float, avg_price: float,
           intent: Intent = Intent.BREAK_EVEN_ON_LOSS, floor: float = 0.0) -> str:
    result = plan_hedge(query, side, shares, avg_price, intent, floor)
    if "error" in result:
        return result["error"]

    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return result["narrative"]  # deterministic, demo-safe

    try:
        import anthropic
        msg = (f"Hedge plan (use verbatim):\n{result['narrative']}\n\n"
               f"Market: {result['market']['question']}")
        resp = anthropic.Anthropic().messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=400,
            system=SYSTEM,
            messages=[{"role": "user", "content": msg}],
        )
        return resp.content[0].text
    except Exception:
        return result["narrative"]
