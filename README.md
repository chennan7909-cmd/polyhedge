> **Live demo:** https://polyhedge.streamlit.app
> **On-chain contract (Base Sepolia):** [`0x6bAeCb1b31Bb340D0C85762a11c3202A7F8087dE`](https://sepolia.basescan.org/address/0x6bAeCb1b31Bb340D0C85762a11c3202A7F8087dE)

# PolyHedge — Agentic Hedging Tool for Polymarket

An AI risk officer for prediction-market positions. Tell it the position you're
worried about; it finds the market, reads live prices, computes how many opposite
shares you'd need to cap your downside or lock a result, and explains the
trade-off in plain language.

**Read-only & simulation.** No wallet, no trade submission, no DeFi protocol.
All trading is simulated, so the demo can't move funds or fail on-chain.

## Why it's honest (and why that wins)

In a single market, `YES_ask + NO_ask > 1` — the spread is the house edge. So a
full in-place hedge usually **locks a small loss, not a profit**. Most naive
"hedging calculators" hide this. PolyHedge detects it and says so, then points
you toward correlated-market hedging. That candor is the differentiator with
finance-literate judges.

## Quickstart

```bash
pip install -r requirements.txt

# Live Polymarket data, deterministic advice (no LLM key required):
python -m polyhedge.demo --query "election" --side YES --shares 100 --price 0.60

# Fully offline (venue-wifi-proof) demo:
python -m polyhedge.demo --mock --side YES --shares 100 --price 0.60 --hedge 0.45

# Natural-language advice via Claude (optional):
export ANTHROPIC_API_KEY=sk-...
python -m polyhedge.demo --query "fed rate cut" --side NO --shares 200 --price 0.30
```

## Hedging intents

| Intent | What it does |
|---|---|
| `break_even_on_loss` | Size hedge so a loss nets ~$0 (cap downside) |
| `lock_profit` | Equalise P/L across both outcomes (fixed result) |
| `custom_floor` | Guarantee worst-case P/L ≥ a floor you set |

## Architecture

```
user prompt
   │
   ▼
agent.py  ── single Claude tool-calling loop (degrades to deterministic)
   │
   ├─ client.py   Gamma API  → market discovery + outcomePrices (PUBLIC, no auth)
   │              CLOB API    → order-book depth for slippage (PUBLIC read)
   │
   └─ hedge.py    pure functions: position P/L, hedge sizing, risk narrative
                  (fully unit-tested — this is the part that must be correct)
```

## API notes (verified May 2026)

- **Gamma** `https://gamma-api.polymarket.com/markets` — public, ~60 req/min,
  no auth. `outcomePrices` = current implied probabilities; `clobTokenIds` maps
  outcomes to CLOB token ids.
- **CLOB** `https://clob.polymarket.com/order-book?token_id=...` — public read.
- Trade submission requires wallet signing — intentionally **not** implemented.

## Tests

```bash
pytest -q
```

## Roadmap (post-hackathon)

- Cross-market correlation hedging (the genuinely "smart" version)
- Slippage-aware sizing from live order-book depth
- Negative-risk arbitrage detection (`sum(outcomePrices) < 0.98`)

## Disclaimer

Educational simulation. Not financial advice. Does not place real trades.


## On-Chain Deployment — Chainlink-Gated Hedge Guard (Base Sepolia)

PolyHedge records every hedge on-chain **only after** validating a live Chainlink price feed. This prevents an agent from settling a hedge against a stale or invalid price — the price check is a hard `require` gate in front of the state-changing write.

### Live contract

| Field | Value |
|---|---|
| **Contract** | `HedgeGuard.sol` (Solidity 0.8.19) |
| **Network** | Base Sepolia (chainId 84532) |
| **Address** | [`0x6bAeCb1b31Bb340D0C85762a11c3202A7F8087dE`](https://sepolia.basescan.org/address/0x6bAeCb1b31Bb340D0C85762a11c3202A7F8087dE) |
| **Chainlink BTC/USD feed** | [`0x0FB99723Aee6f420beAD13e6bBB79b7E6F034298`](https://sepolia.basescan.org/address/0x0FB99723Aee6f420beAD13e6bBB79b7E6F034298) |
| **Deploy tx** | [`0x723ed4dd...b961da8`](https://sepolia.basescan.org/tx/0x723ed4ddefb7224152364032e1401ff3cdad243224f0aea379f3077d7b961da8) |

### How the Chainlink integration works

`getValidatedPrice()` reads `latestRoundData()` from the Chainlink BTC/USD aggregator and enforces four checks before returning the price:

- `answer > 0` — price must be positive
- `updatedAt != 0` — round must be complete
- `answeredInRound >= roundId` — round must not be stale
- `block.timestamp - updatedAt <= 3 hours` — price must be fresh

`recordHedge(market, shares)` calls `getValidatedPrice()` first; if the feed fails any check the whole transaction reverts and **no hedge is written**. On success it stores the hedge plus the Chainlink price that gated it, and emits `HedgeRecorded`.

### Verified live run

Read (free view call):

    getValidatedPrice() -> 6427955000000  =  BTC/USD $64,279.55

Write (real on-chain hedge, gated by the price above):

    recordHedge("BTC reach $67,500 in June", 100)  ->  Status: SUCCESS
    tx: 0x8183934ad31369d15e534e2ea03d1107c1d898c1f36920340b42cf42e7e8aea3

[View hedge tx on Basescan](https://sepolia.basescan.org/tx/0x8183934ad31369d15e534e2ea03d1107c1d898c1f36920340b42cf42e7e8aea3)

On-chain state after the run:

    hedgeCount() = 1
    hedges(0)    = [0x0744...3385, "BTC reach $67,500 in June", 100, 6427955000000, 1781380396]
                   (account, market, shares, guardPrice $64,279.55, timestamp)

The stored `guardPrice` ($64,279.55) is the Chainlink value captured at execution — proof that the hedge was committed against a validated, fresh price.

### Reproduce

    pip install "web3>=6.0" py-solc-x
    export PRIVATE_KEY="0x<your_test_wallet_key>"
    cd deploy
    python deploy.py      # compiles + deploys HedgeGuard
    python interact.py    # reads validated price, sends a real recordHedge tx


## Agentic Execution -- Dynamic Server Wallets (Best Agentic Build)

PolyHedge is not just an advisor -- it is an **agent that acts on-chain by itself**. It decides whether a hedge is safe, then signs and broadcasts the transaction through a **Dynamic server wallet** (MPC), with no human key handling.

### How it works

1. **Decide.** The PolyHedge engine evaluates the position -- five-dimension relationship check plus the live Chainlink price gate -- and decides whether the hedge is real and safe to record.
2. **Sign (Dynamic).** If the agent decides to act, it signs the recordHedge transaction with a Dynamic **server wallet** created and controlled entirely from the Python backend. Signing uses MPC (TWO_OF_TWO): the server and Dynamic each hold part of the key, so no full private key exists anywhere.
3. **Execute.** The signed transaction is broadcast to Base Sepolia and lands in the Chainlink-gated HedgeGuard contract.

The agent's wallet is its own -- created via create_wallet_account, funded with gas, and used to transact autonomously.

### Verified agentic run

    [agent] Evaluating hedge for: BTC reach $67,500 in June
    [agent] Engine verdict: hedge is valid (Chainlink-gated, settlement-checked).
    [agent] Decision: RECORD HEDGE ON-CHAIN.
    [server wallet] 0x349c04Da35711EC8AA21b9c5DdDDb78424B3C6AC
    [agent] Signing + broadcasting recordHedge via Dynamic server wallet...
    === AGENT EXECUTED ONCHAIN === Status: SUCCESS

- **Server wallet (agent):** 0x349c04Da35711EC8AA21b9c5DdDDb78424B3C6AC
- **Agentic tx:** https://sepolia.basescan.org/tx/0xd4375d38679e9ef4d12e4eef7f6bafa240dc757548074ab01c4bc15a52b3e5c3
- **SDK:** dynamic-wallet-sdk (Python, server-side MPC)
- **Chain:** Base Sepolia (84532)

The same recordHedge call is gated by Chainlink inside the contract, so this single transaction exercises both the Dynamic agentic path and the Chainlink price validation.

### Reproduce

    pip install dynamic-wallet-sdk
    export DYNAMIC_ENV_ID="<your_environment_id>"
    export DYNAMIC_API_TOKEN="<your_api_token>"
    export DYNAMIC_WALLET_PASSWORD="<your_wallet_password>"
    cd deploy
    python3 dynamic_create_wallet.py   # agent creates its own server wallet
    # fund the printed address with Base Sepolia ETH
    python3 dynamic_agent_hedge.py     # agent decides, signs, and executes on-chain
