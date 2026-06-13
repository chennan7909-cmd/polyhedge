"""PolyHedge - Streamlit demo UI.

Runs on a curated snapshot of real Polymarket data so the demo is reproducible
and reliable for recording. Reuses the hedge engine (cost-ratio guardrail) and
the four-dimension relationship classifier from the package.
"""
import streamlit as st

from polyhedge.hedge import (Position, Side, Intent, compute_hedge,
                             compute_lock_profit_hedge, narrate)
from polyhedge.client import Market
from polyhedge.market_structure import (
    parse_market, classify_relationship, Relationship,
)


def mk(mid, question, yes, no, resolution_source=None):
    return Market(
        id=mid, question=question, slug=mid, outcomes=["Yes", "No"],
        prices=[yes, no], token_ids=["a", "b"], volume=0.0, liquidity=500000.0,
        end_date=None, neg_risk=False, raw={"resolution_source": resolution_source},
    )


# --- Curated snapshot of real Polymarket markets (prices pulled this week) ---
MKT_SPURS = mk("spurs_champ", "Will the San Antonio Spurs win the 2026 NBA Finals?", 0.198, 0.802)
MKT_KNICKS = mk("knicks_champ", "Will the New York Knicks win the 2026 NBA Finals?", 0.802, 0.198)
MKT_BTC_675 = mk("btc_675_june", "Will Bitcoin reach \$67,500 in June?", 0.435, 0.565,
                 resolution_source="Coinbase BTC-USD")
MKT_BTC_675_BINANCE = mk("btc_675_june_binance", "Will Bitcoin reach \$67,500 in June?", 0.44, 0.56,
                         resolution_source="Binance BTC-USDT")
MKT_BTC_DIP55 = mk("btc_dip55_june", "Will Bitcoin dip to $55,000 in June?", 0.16, 0.84)
MKT_BTC_EXPIRY = mk("btc_above675_jun30", "Will Bitcoin be above $67,500 on June 30?", 0.46, 0.54)

REL_LABEL = {
    Relationship.SAME_MARKET: "Same-market exact hedge",
    Relationship.COMPATIBLE_CROSS_MARKET: "Compatible cross-market hedge",
    Relationship.RELATED_NOT_HEDGE: "Related, but not a hedge",
    Relationship.REJECTED: "Rejected",
}


st.set_page_config(page_title="PolyHedge", page_icon="🛡️", layout="centered")
st.title("🛡️ PolyHedge")
st.caption("An AI risk officer for on-chain prediction markets")

scenario = st.radio(
    "Choose a scenario",
    ["Spurs position - cost guardrail",
     "Bitcoin - exact same-market hedge",
     "Bitcoin - reject an unsafe cross-market hedge"],
)

st.divider()

if scenario.startswith("Spurs"):
    st.subheader("Spurs championship position")
    st.write("You hold **100 YES shares** on the Spurs to win the title, "
             "entered at **\$0.20** (a \$20 position). After Game 4, panic says: hedge now.")
    pos = Position(side=Side.YES, shares=100, avg_price=0.20)
    # Hedge would be buying the opposite outcome (Knicks ~0.80).
    plan = compute_hedge(pos, hedge_price=0.80, intent=Intent.BREAK_EVEN_ON_LOSS)
    if st.button("Ask PolyHedge to hedge"):
        st.text(narrate(pos, plan))
        if plan.hedge_shares == 0:
            st.error("Hedge NOT recommended - the protection costs more than the risk.")
        else:
            st.success("Hedge recommended.")

elif scenario.startswith("Bitcoin - exact"):
    st.subheader("Bitcoin: reach \$67,500 in June - lock in a gain")
    st.write("You bought **100 YES shares** early at **\$0.30** (cost \$30). "
             "The market has since risen to **\$0.55** - you're up on paper. "
             "But Bitcoin is volatile and you don't want to give the gain back. "
             "The cleanest hedge is the opposite side of the *same* market - zero basis risk.")
    pos = Position(side=Side.YES, shares=100, avg_price=0.30, mark_price=0.55)
    plan = compute_lock_profit_hedge(pos, hedge_price=0.45)
    if st.button("Lock in the gain"):
        st.text(narrate(pos, plan))
        if plan.hedge_shares > 0:
            st.success("Exact same-market hedge: buying the opposite side locks in a "
                       "positive floor. Same resolution, same settlement, zero basis risk.")
        else:
            st.error(plan.note or "Hedge not recommended.")

else:
    st.subheader("Bitcoin: should we hedge across markets?")
    st.write("Your position: **Bitcoin reach \$67,500 in June** (a *touch* market). "
             "PolyHedge checks candidate markets before trusting any of them.")
    position = parse_market(MKT_BTC_675)
    candidates = [MKT_BTC_675_BINANCE, MKT_BTC_DIP55, MKT_BTC_EXPIRY,
                  mk("eth_4000", "Will Ethereum reach $4,000 in June?", 0.41, 0.59)]
    if st.button("Scan curated candidate pool"):
        for cand_mkt in candidates:
            cand = parse_market(cand_mkt)
            rel, why = classify_relationship(position, cand)
            label = REL_LABEL[rel]
            line = f"**{cand_mkt.question}**  \n{label} - {why}"
            if rel == Relationship.REJECTED:
                st.error(line)
            elif rel == Relationship.COMPATIBLE_CROSS_MARKET:
                st.success(line)
            else:
                st.warning(line)
        st.caption("Note the at-expiry market is rejected: it settles on one day, "
                   "while the position settles on a touch any time in June. That "
                   "mismatch is basis risk.")

st.divider()
st.caption("Curated snapshot of real Polymarket data, for a reproducible demo.")
