"""Hedging math for binary (YES/NO) prediction-market positions."""
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
    avg_price: float
    mark_price: float = 0.0  # current market price; 0 means "same as avg_price"

    @property
    def cost(self) -> float:
        return self.shares * self.avg_price

    @property
    def mark(self) -> float:
        return self.mark_price if self.mark_price > 0 else self.avg_price

    @property
    def unrealized_pnl(self) -> float:
        # Paper gain/loss if you sold at the current market price now.
        return self.shares * (self.mark - self.avg_price)

    def pnl_if_win(self) -> float:
        return self.shares * (1 - self.avg_price)

    def pnl_if_lose(self) -> float:
        return -self.cost


@dataclass
class HedgePlan:
    hedge_side: Side
    hedge_price: float
    hedge_shares: float
    hedge_cost: float
    pnl_if_original_wins: float
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
    win = pos.pnl_if_win() + (-x * h)
    lose = pos.pnl_if_lose() + (x * (1 - h))
    return win, lose


def compute_hedge(pos: Position, hedge_price: float,
                  intent: Intent = Intent.BREAK_EVEN_ON_LOSS,
                  floor: float = 0.0) -> HedgePlan:
    if not (0 < hedge_price < 1):
        raise ValueError("hedge_price must be between 0 and 1")

    if hedge_price >= 0.90:
        implied_win_prob = round((1 - hedge_price) * 100)
        return HedgePlan(
            hedge_side=Side.NO if pos.side == Side.YES else Side.YES,
            hedge_price=hedge_price, hedge_shares=0.0, hedge_cost=0.0,
            pnl_if_original_wins=round(pos.pnl_if_win(), 2),
            pnl_if_original_loses=round(pos.pnl_if_lose(), 2),
            intent=intent,
            note=(f"The market implies your side is already ~{100 - implied_win_prob}% "
                  f"likely to win, so the hedge outcome costs ${hedge_price:.2f}. "
                  "A hedge here would cost far more than the small loss it protects "
                  "against, and you would give up most of your upside. Not worth "
                  "hedging in this market; look for a correlated market where your "
                  "risk is priced more evenly."),
        )

    hedge_side = Side.NO if pos.side == Side.YES else Side.YES

    if intent == Intent.BREAK_EVEN_ON_LOSS:
        x = pos.cost / (1 - hedge_price)
    elif intent == Intent.LOCK_PROFIT:
        x = pos.shares
    elif intent == Intent.CUSTOM_FLOOR:
        x = (pos.cost + floor) / (1 - hedge_price)
    else:
        raise ValueError(f"unknown intent {intent}")

    x = max(x, 0.0)
    win, lose = _combined(pos, x, hedge_price)
    cost = x * hedge_price

    # --- Cost-to-loss ratio guardrail ---
    # The most you can lose unhedged is pos.cost. If the hedge costs more than
    # the loss it removes, buying protection is irrational. Catch this even when
    # hedge_price < 0.90.
    MAX_COST_TO_LOSS_RATIO = 1.0
    protected_loss = pos.cost
    if protected_loss > 0 and cost > protected_loss * MAX_COST_TO_LOSS_RATIO:
        ratio = cost / protected_loss
        return HedgePlan(
            hedge_side=hedge_side, hedge_price=hedge_price,
            hedge_shares=0.0, hedge_cost=0.0,
            pnl_if_original_wins=round(pos.pnl_if_win(), 2),
            pnl_if_original_loses=round(pos.pnl_if_lose(), 2),
            intent=intent,
            note=(f"Hedging this position would cost ${cost:.2f} to protect a "
                  f"maximum loss of ${protected_loss:.2f} - about {ratio:.1f}x the "
                  "risk it removes. The protection costs more than the downside, "
                  "so hedging is not worth it here."),
        )

    note = ""
    if win < 0 and lose < 0:
        note = ("Both outcomes net a loss; the hedge price is too rich to break "
                "even. This is the market's spread working against you; consider a "
                "cheaper correlated market instead of hedging in-place.")
    elif intent == Intent.LOCK_PROFIT and win < 0:
        note = ("Locked result is negative. In a single market YES+NO asks exceed "
                "$1, so a full hedge locks a small loss, not a profit.")

    return HedgePlan(
        hedge_side=hedge_side, hedge_price=hedge_price,
        hedge_shares=round(x, 2), hedge_cost=round(cost, 2),
        pnl_if_original_wins=round(win, 2),
        pnl_if_original_loses=round(lose, 2),
        intent=intent, note=note,
    )


def narrate(pos: Position, plan: HedgePlan) -> str:
    naked_win = round(pos.pnl_if_win(), 2)
    naked_lose = round(pos.pnl_if_lose(), 2)
    upside_given_up = round(naked_win - plan.pnl_if_original_wins, 2)
    lines = [
        f"Position: {pos.shares:g} {pos.side.value} shares @ ${pos.avg_price:.2f} "
        f"(cost ${pos.cost:.2f}).",
        f"Unhedged: +${naked_win} if it resolves your way, ${naked_lose} if not.",
    ]
    if plan.hedge_shares == 0:
        lines.append(f"No useful hedge available.")
    else:
        lines.append(
            f"Hedge: buy {plan.hedge_shares:g} {plan.hedge_side.value} shares @ "
            f"${plan.hedge_price:.2f} (cost ${plan.hedge_cost}).")
        lines.append(
            f"After hedging: ${plan.pnl_if_original_wins} if original wins, "
            f"${plan.pnl_if_original_loses} if it loses.")
        lines.append(
            f"You trade away ${upside_given_up} of upside to set a floor of "
            f"${plan.worst_case}. That is the cost of certainty.")
    if plan.note:
        lines.append(f"NOTE: {plan.note}")
    return "\n".join(lines)



def compute_lock_profit_hedge(pos: Position, hedge_price: float) -> HedgePlan:
    """Lock in an unrealized gain by buying the opposite side.

    Use when the position's mark price is above its cost: the holder is up on
    paper and wants to secure that gain regardless of outcome. We size the hedge
    so the two outcomes are balanced, then report the locked result. If the
    locked result is not positive, we honestly say it is not worth it yet.
    """
    if not (0 < hedge_price < 1):
        raise ValueError("hedge_price must be between 0 and 1")

    hedge_side = Side.NO if pos.side == Side.YES else Side.YES
    n = pos.shares

    # Payoff if original wins:  n*(1-avg) - x*hedge_price
    # Payoff if original loses: -n*avg   + x*(1-hedge_price)
    # Set equal and solve for x to balance both outcomes:
    #   n*(1-avg) - x*hp = -n*avg + x*(1-hp)
    #   n*(1-avg) + n*avg = x*(1-hp) + x*hp
    #   n = x   ->  balanced hedge buys x shares solving below
    # Solve generally:
    x = (n * (1 - pos.avg_price) + n * pos.avg_price) / 1.0  # = n
    # The balanced quantity is n; locked value is symmetric. Compute both ends.
    x = n
    cost = x * hedge_price
    win = n * (1 - pos.avg_price) - x * hedge_price
    lose = -n * pos.avg_price + x * (1 - hedge_price)
    locked = min(win, lose)

    if locked <= 0:
        return HedgePlan(
            hedge_side=hedge_side, hedge_price=hedge_price,
            hedge_shares=0.0, hedge_cost=0.0,
            pnl_if_original_wins=round(pos.pnl_if_win(), 2),
            pnl_if_original_loses=round(pos.pnl_if_lose(), 2),
            intent=Intent.LOCK_PROFIT,
            note=("Locking now would not secure a positive result yet: the market "
                  "has not moved far enough above your cost to lock a gain. Hold, or "
                  "wait for a better price."),
        )

    return HedgePlan(
        hedge_side=hedge_side, hedge_price=hedge_price,
        hedge_shares=round(x, 2), hedge_cost=round(cost, 2),
        pnl_if_original_wins=round(win, 2),
        pnl_if_original_loses=round(lose, 2),
        intent=Intent.LOCK_PROFIT,
        note=(f"You're up ${pos.unrealized_pnl:.2f} on paper. Buying {x:g} "
              f"{hedge_side.value} shares @ ${hedge_price:.2f} locks in ${locked:.2f} "
              "no matter how it resolves. You give up further upside to bank the gain."),
    )