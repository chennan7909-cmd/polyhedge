"""Tests for lock-profit hedging."""
from polyhedge.hedge import Position, Side, compute_lock_profit_hedge


def test_locks_positive_floor_when_in_profit():
    # Bought at 0.30, now marked 0.55. Hedge at 0.45 should lock a positive floor.
    pos = Position(side=Side.YES, shares=100, avg_price=0.30, mark_price=0.55)
    plan = compute_lock_profit_hedge(pos, hedge_price=0.45)
    assert plan.hedge_shares > 0
    assert plan.worst_case > 0
    assert plan.pnl_if_original_wins > 0 and plan.pnl_if_original_loses > 0


def test_declines_when_no_gain_to_lock():
    # No paper gain and an expensive hedge -> cannot lock a positive result.
    pos = Position(side=Side.YES, shares=100, avg_price=0.50, mark_price=0.50)
    plan = compute_lock_profit_hedge(pos, hedge_price=0.55)
    assert plan.hedge_shares == 0
    assert "not secure a positive result" in plan.note
