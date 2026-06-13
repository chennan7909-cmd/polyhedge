"""Tests for the cost-to-loss ratio guardrail in compute_hedge."""
from polyhedge.hedge import Position, Side, Intent, compute_hedge


def test_rejects_hedge_costing_more_than_loss():
    # 100 YES @ 0.20 => max loss $20. Hedging at 0.80 costs ~$81 (4x). Reject.
    pos = Position(side=Side.YES, shares=100, avg_price=0.20)
    plan = compute_hedge(pos, hedge_price=0.80, intent=Intent.BREAK_EVEN_ON_LOSS)
    assert plan.hedge_shares == 0.0
    assert plan.hedge_cost == 0.0
    assert "more than the downside" in plan.note


def test_allows_economical_hedge():
    # 100 YES @ 0.60 => max loss $60. Hedging at 0.45 is far cheaper than $60.
    pos = Position(side=Side.YES, shares=100, avg_price=0.60)
    plan = compute_hedge(pos, hedge_price=0.45, intent=Intent.BREAK_EVEN_ON_LOSS)
    assert plan.hedge_shares > 0.0
    assert plan.hedge_cost < pos.cost
