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
