"""Tests for market structure parsing (asset, threshold, direction, settlement)."""
from polyhedge.client import Market
from polyhedge.market_structure import parse_market, Settlement, Direction


def _mk(question: str) -> Market:
    return Market(
        id="x", question=question, slug="x", outcomes=["Yes", "No"],
        prices=[0.5, 0.5], token_ids=["a", "b"], volume=0.0, liquidity=0.0,
        end_date=None, neg_risk=False, raw={},
    )


def test_touch_market():
    s = parse_market(_mk("Will Bitcoin reach $67,500 in June?"))
    assert s.asset == "BTC"
    assert s.threshold == 67500.0
    assert s.direction == Direction.ABOVE
    assert s.settlement == Settlement.TOUCH


def test_at_expiry_market():
    s = parse_market(_mk("Will the price of Bitcoin be above $68,000 on June 12?"))
    assert s.asset == "BTC"
    assert s.settlement == Settlement.AT_EXPIRY


def test_dip_market_is_bearish_touch():
    s = parse_market(_mk("Will Bitcoin dip to $55,000 in June?"))
    assert s.direction == Direction.BELOW
    assert s.settlement == Settlement.TOUCH


def test_touch_vs_at_expiry_differ():
    # The core basis-risk signal: same asset, different settlement.
    touch = parse_market(_mk("Will Bitcoin reach $67,500 in June?"))
    expiry = parse_market(_mk("Will Bitcoin be above $67,500 on June 30?"))
    assert touch.settlement != expiry.settlement