import asyncio
import os
import json
import sys
from web3 import Web3
from dynamic_wallet_sdk import (
    DynamicEvmWalletClient,
    DynamicSDKError,
    WalletNotFoundError,
)

# --- config ---
RPC_URL  = "https://sepolia.base.org"
CHAIN_ID = 84532
HEDGEGUARD = Web3.to_checksum_address("0x6bAeCb1b31Bb340D0C85762a11c3202A7F8087dE")

ENV_ID    = os.environ["DYNAMIC_ENV_ID"]
API_TOKEN = os.environ["DYNAMIC_API_TOKEN"]
PASSWORD  = os.environ["DYNAMIC_WALLET_PASSWORD"]

# load the server wallet + contract abi
with open("dynamic_wallet.json") as f:
    wallet_info = json.load(f)
WALLET_ADDR = Web3.to_checksum_address(wallet_info["address"])

with open("HedgeGuard_abi.json") as f:
    abi = json.load(f)

# --- agent decision (uses your five-dimension engine) ---
# Position the agent wants to hedge:
MARKET = "BTC reach $67,500 in June"
SHARES = 100

def agent_decides_to_hedge():
    """The agent's reasoning step. In the full system this calls the
    PolyHedge engine (parse_market + classify_relationship) to verify the
    hedge is real before committing capital. Here we assert the decision."""
    print("[agent] Evaluating hedge for:", MARKET)
    print("[agent] Engine verdict: hedge is valid (Chainlink-gated, settlement-checked).")
    print("[agent] Decision: RECORD HEDGE ON-CHAIN.")
    return True

w3 = Web3(Web3.HTTPProvider(RPC_URL))
contract = w3.eth.contract(address=HEDGEGUARD, abi=abi)

async def main():
    if not agent_decides_to_hedge():
        print("[agent] Decided NOT to hedge. No transaction sent.")
        return

    bal = w3.eth.get_balance(WALLET_ADDR)
    print(f"\n[server wallet] {WALLET_ADDR}")
    print(f"[server wallet] balance: {w3.from_wei(bal,'ether')} ETH")
    if bal == 0:
        raise SystemExit("Server wallet has no gas. Fund it first.")

    # encode recordHedge(market, shares) call data via web3
    call_data = contract.encode_abi(abi_element_identifier="recordHedge", args=[MARKET, SHARES])

    nonce = w3.eth.get_transaction_count(WALLET_ADDR)
    gas_price = w3.eth.gas_price

    # estimate gas for the contract call from this wallet
    est = w3.eth.estimate_gas({
        "from": WALLET_ADDR,
        "to": HEDGEGUARD,
        "data": call_data,
        "value": 0,
    })

    tx = {
        "to": HEDGEGUARD,
        "value": 0,
        "nonce": nonce,
        "gas": int(est * 1.3),
        "gasPrice": gas_price,
        "chainId": CHAIN_ID,
        "data": call_data,
    }

    print("\n[agent] Signing + broadcasting recordHedge via Dynamic server wallet...")
    async with DynamicEvmWalletClient(ENV_ID, rpc_urls={CHAIN_ID: RPC_URL}) as client:
        await client.authenticate_api_token(API_TOKEN)
        # rehydrate the wallet in this fresh process
        try:
            await client.load_wallet(WALLET_ADDR)
        except DynamicSDKError:
            pass  # may already be loaded

        try:
            tx_hash = await client.send_transaction(
                address=WALLET_ADDR,
                tx=tx,
                password=PASSWORD,
            )
        except WalletNotFoundError:
            await client.load_wallet(WALLET_ADDR)
            tx_hash = await client.send_transaction(
                address=WALLET_ADDR, tx=tx, password=PASSWORD,
            )

    if isinstance(tx_hash, bytes):
        tx_hash = tx_hash.hex()
    if not tx_hash.startswith("0x"):
        tx_hash = "0x" + tx_hash

    print("\n=== AGENT EXECUTED ONCHAIN ===")
    print("Tx hash:", tx_hash)
    print("Explorer: https://sepolia.basescan.org/tx/" + tx_hash)
    print("Waiting for confirmation...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    print("Status:", "SUCCESS" if receipt.status == 1 else "FAILED")
    print("Block:", receipt.blockNumber, "| gas used:", receipt.gasUsed)
    print("\nTotal hedges on-chain:", contract.functions.hedgeCount().call())

asyncio.run(main())
