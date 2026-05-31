"""
Demo CLI.  Examples:

    # Live data, deterministic advice (no LLM key needed):
    python -m polyhedge.demo --query "election" --side YES --shares 100 --price 0.60

    # Offline mock (no network) — perfect when the venue wifi dies on stage:
    python -m polyhedge.demo --mock --side YES --shares 100 --price 0.60 --hedge 0.45
"""
from __future__ import annotations

import argparse

from .hedge import Position, Side, Intent, compute_hedge, narrate


def _mock(side: Side, shares: float, price: float, hedge: float, intent: Intent, floor: float):
    pos = Position(side=side, shares=shares, avg_price=price)
    plan = compute_hedge(pos, hedge, intent=intent, floor=floor)
    print(narrate(pos, plan))


def main() -> None:
    ap = argparse.ArgumentParser(description="PolyHedge — agentic hedging for Polymarket")
    ap.add_argument("--query", default="election", help="market search text")
    ap.add_argument("--side", choices=["YES", "NO"], default="YES")
    ap.add_argument("--shares", type=float, default=100)
    ap.add_argument("--price", type=float, default=0.60, help="your avg entry price")
    ap.add_argument("--intent", choices=[i.value for i in Intent],
                    default=Intent.BREAK_EVEN_ON_LOSS.value)
    ap.add_argument("--floor", type=float, default=0.0)
    ap.add_argument("--mock", action="store_true", help="use a fixed hedge price, no network")
    ap.add_argument("--hedge", type=float, default=0.45, help="mock hedge price")
    args = ap.parse_args()

    side = Side(args.side)
    intent = Intent(args.intent)

    if args.mock:
        _mock(side, args.shares, args.price, args.hedge, intent, args.floor)
        return

    from .agent import advise
    print(advise(args.query, side, args.shares, args.price, intent, args.floor))


if __name__ == "__main__":
    main()
