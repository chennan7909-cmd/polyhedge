"""Tests for hedge relationship classification (the four-dimension check)."""
from polyhedge.client import Market
from polyhedge.market_structure import (
    parse_market, classify_relationship, Relationship,
)


def _mk(mid: str, question: str) -> Market:
    return Market(
        id=mid, question=question, slug=mid, outcomes=["Yes", "No"],
        prices=[0.5, 0.5], token_ids=["a", "b"], volume=0.0, liquidity=0.0,
        end_date=None, neg_risk=False, raw={},
    )


def _s(mid, q):
    return parse_market(_mk(mid, q))


def test_same_market_is_exact_hedge():
    pos = _s("m1", "Will Bitcoin reach $67,500 in June?")
    rel, why = classify_relationship(pos, pos)
    assert rel == Relationship.SAME_MARKET


def test_at_expiry_candidate_rejected_for_basis_risk():
    # The core demo gate: touch position vs at-expiry candidate = basis risk.
    pos = _s("m1", "Will Bitcoin reach $67,500 in June?")
    cand = _s("m2", "Will Bitcoin be above $68,000 on June 30?")
    rel, why = classify_relationship(pos, cand)
    assert rel == Relationship.REJECTED
    assert "basis risk" in why


def test_different_asset_rejected():
    pos = _s("m1", "Will Bitcoin reach $67,500 in June?")
    cand = _s("m2", "Will Ethereum reach $4,000 in June?")
    rel, why = classify_relationship(pos, cand)
    assert rel == Relationship.REJECTED
    assert "asset mismatch" in why


def test_same_direction_is_related_not_hedge():
    # Both bullish touch -> correlated, not an offsetting hedge.
    pos = _s("m1", "Will Bitcoin reach $67,500 in June?")
    cand = _s("m2", "Will Bitcoin reach $65,000 in June?")
    rel, why = classify_relationship(pos, cand)
    assert rel == Relationship.RELATED_NOT_HEDGE


def test_opposite_direction_compatible():
    # Bullish touch position, bearish touch candidate, same asset/window/settlement.
    pos = _s("m1", "Will Bitcoin reach $67,500 in June?")
    cand = _s("m2", "Will Bitcoin dip to $55,000 in June?")
    rel, why = classify_relationship(pos, cand)
    assert rel == Relationship.COMPATIBLE_CROSS_MARKET