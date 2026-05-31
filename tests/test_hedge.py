from polyhedge.hedge import (
    Position, Side, Intent, compute_hedge, narrate,
)


def test_break_even_on_loss_zeroes_the_loss_branch():
    pos = Position(side=Side.YES, shares=100, avg_price=0.60)  # cost 60
    plan = compute_hedge(pos, hedge_price=0.45, intent=Intent.BREAK_EVEN_ON_LOSS)
    # x = 60 / (1 - 0.45) = 109.09
    assert abs(plan.hedge_shares - 109.09) < 0.05
    assert abs(plan.pnl_if_original_loses) < 0.01   # ~0 on loss
    # win branch must drop relative to naked +40
    assert plan.pnl_if_original_wins < pos.pnl_if_win()


def test_lock_profit_equalises_branches():
    pos = Position(side=Side.YES, shares=100, avg_price=0.40)
    plan = compute_hedge(pos, hedge_price=0.55, intent=Intent.LOCK_PROFIT)
    assert plan.hedge_shares == 100  # 1:1
    assert abs(plan.pnl_if_original_wins - plan.pnl_if_original_loses) < 0.01


def test_full_hedge_in_single_market_locks_a_loss_when_asks_exceed_one():
    # YES@0.60 + NO@0.45 = 1.05 -> overpriced book, locking loses money
    pos = Position(side=Side.YES, shares=100, avg_price=0.60)
    plan = compute_hedge(pos, hedge_price=0.45, intent=Intent.LOCK_PROFIT)
    assert plan.pnl_if_original_wins < 0
    assert "locks a small loss" in plan.note or plan.note != ""


def test_custom_floor_respected():
    pos = Position(side=Side.NO, shares=80, avg_price=0.30)  # cost 24
    plan = compute_hedge(pos, hedge_price=0.50, intent=Intent.CUSTOM_FLOOR, floor=-5)
    assert plan.worst_case >= -5.01


def test_narrative_mentions_certainty_tradeoff():
    pos = Position(side=Side.YES, shares=100, avg_price=0.60)
    plan = compute_hedge(pos, hedge_price=0.45)
    text = narrate(pos, plan)
    assert "cost of certainty" in text
    assert "floor" in text


def test_rejects_bad_price():
    pos = Position(side=Side.YES, shares=10, avg_price=0.5)
    for bad in (0.0, 1.0, 1.5, -0.1):
        try:
            compute_hedge(pos, hedge_price=bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")
