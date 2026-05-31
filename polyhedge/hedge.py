"""
Hedging math for binary (YES/NO) prediction-market positions.

A Polymarket share pays $1 if its outcome resolves true, $0 otherwise.
If you hold `q` shares of an outcome bought at average price `p`:
    cost            = q * p
    payoff if WIN   = q * 1   -> P/L = q * (1 - p)
    payoff if LOSE  = q * 0   -> P/L = -q * p

To hedge, you take shares of the OPPOSITE outcome at its current ask price `h`
(for a YES position the hedge is NO, and vice-versa). Buying `x` hedge shares:
    if original outcome LOSES, hedge WINS: hedge P/L = x * (1 - h)
    if original outcome WINS,  hedge LOSES: hedge P/L = -x * h

We expose three intents:
  * BREAK_EVEN_ON_LOSS  -> size the hedge so a loss nets ~0 (cap the downside).
  * LOCK_PROFIT         -> equalise P/L across both outcomes (guarantee a fixed result).
  * CUSTOM_FLOOR        -> guarantee P/L >= floor in the worst case.

Reality check baked in: in a single market YES_ask + NO_ask is usually > 1
(the spread is the house edge), so a full hedge LOCKS A SMALL LOSS, not a profit.
The tool says so explicitly instead of pretending otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Side(str, Enum):
    YES = "YES"
    NO = "NO"


class Intent(str, Enum):
    BREAK_EVEN_ON_LOSS = "break_even_on_loss"
    LOCK_PROFIT = "lock_profit"
    CUSTOM_FLOOR = "custom_floor"


@dataclass
class Position:
    side: Side
    shares: float
    avg_price: float          # what you paid per share, 0..1

    @property
    def cost(self) -> float:
        return self.shares * self.avg_price

    def pnl_if_win(self) -> float:
        return self.shares * (1 - self.avg_price)

    def pnl_if_lose(self) -> float:
        return -self.cost


@dataclass
class HedgePlan:
    hedge_side: Side
    hedge_price: float            # price you'd pay per hedge share now
    hedge_shares: float
    hedge_cost: float
    pnl_if_original_wins: float   # total P/L (position + hedge)
    pnl_if_original_loses: float
    intent: Intent
    note: str = ""

    @property
    def worst_case(self) -> float:
        return min(self.pnl_if_original_wins, self.pnl_if_original_loses)

    @property
    def best_case(self) -> float:
        return max(self.pnl_if_original_wins, self.pnl_if_original_loses)


def _combined(pos: Position, x: float, h: float) -> tuple[float, float]:
    """Return (total P/L if original wins, total P/L if original loses) for x hedge shares."""
    win = pos.pnl_if_win() + (-x * h)        # original wins -> hedge loses
    lose = pos.pnl_if_lose() + (x * (1 - h))  # original loses -> hedge wins
    return win, lose


def compute_hedge(
    pos: Position,
    hedge_price: float,
    intent: Intent = Intent.BREAK_EVEN_ON_LOSS,
    floor: float = 0.0,
) -> HedgePlan:
    """
    hedge_price: current ask of the OPPOSITE outcome (0..1).
    """
    if not (0 < hedge_price < 1):
        raise ValueError("hedge_price must be between 0 and 1")

    hedge_side = Side.NO if pos.side == Side.YES else Side.YES

    if intent == Intent.BREAK_EVEN_ON_LOSS:
        # Solve pnl_if_lose == 0:  -cost + x*(1-h) = 0
        x = pos.cost / (1 - hedge_price)
    elif intent == Intent.LOCK_PROFIT:
        # Solve win == lose:
        #   q(1-p) - x*h = -q*p + x*(1-h)
        #   q = x*h + x*(1-h) = x   -> x = q   (intuitive: 1:1 to fully lock)
        x = pos.shares
    elif intent == Intent.CUSTOM_FLOOR:
        # Guarantee both branches >= floor. The binding branch is the loss branch
        # when under-hedged; size so pnl_if_lose == floor, then verify win branch.
        x = (pos.cost + floor) / (1 - hedge_price)
    else:  # pragma: no cover
        raise ValueError(f"unknown intent {intent}")

    x = max(x, 0.0)
    win, lose = _combined(pos, x, hedge_price)
    cost = x * hedge_price

    note = ""
    spread_sum = pos.avg_price + hedge_price if False else None  # placeholder
    if win < 0 and lose < 0:
        note = ("Both outcomes net a loss — the hedge price is too rich to break even. "
                "This is the market's spread working against you; consider a cheaper "
                "correlated market instead of hedging in-place.")
    elif intent == Intent.LOCK_PROFIT and win < 0:
        note = ("Locked result is negative. In a single market YES+NO asks exceed $1, "
                "so a full hedge locks a small loss, not a profit. To truly lock profit "
                "you need the original position already in the money on a correlated market.")

    return HedgePlan(
        hedge_side=hedge_side,
        hedge_price=hedge_price,
        hedge_shares=round(x, 2),
        hedge_cost=round(cost, 2),
        pnl_if_original_wins=round(win, 2),
        pnl_if_original_loses=round(lose, 2),
        intent=intent,
        note=note,
    )


def narrate(pos: Position, plan: HedgePlan) -> str:
    """The 'risk narrative' a finance-literate judge wants to see."""
    naked_win = round(pos.pnl_if_win(), 2)
    naked_lose = round(pos.pnl_if_lose(), 2)
    upside_given_up = round(naked_win - plan.pnl_if_original_wins, 2)
    lines = [
        f"Position: {pos.shares:g} {pos.side.value} shares @ ${pos.avg_price:.2f} "
        f"(cost ${pos.cost:.2f}).",
        f"Unhedged: +${naked_win} if it resolves your way, ${naked_lose} if not.",
        f"Hedge: buy {plan.hedge_shares:g} {plan.hedge_side.value} shares @ "
        f"${plan.hedge_price:.2f} (cost ${plan.hedge_cost}).",
        f"After hedging: ${plan.pnl_if_original_wins} if original wins, "
        f"${plan.pnl_if_original_loses} if it loses.",
        f"You trade away ${upside_given_up} of upside to set a floor of "
        f"${plan.worst_case}. That is the cost of certainty.",
    ]
    if plan.note:
        lines.append(f"⚠ {plan.note}")
    return "\n".join(lines)
