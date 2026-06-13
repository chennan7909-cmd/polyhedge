import os
import json
from web3 import Web3

RPC_URL  = "https://sepolia.base.org"
CHAIN_ID = 84532

with open("deployment.json") as f:
    dep = json.load(f)
with open("HedgeGuard_abi.json") as f:
    abi = json.load(f)

ADDRESS = Web3.to_checksum_address(dep["address"])

pk = os.environ.get("PRIVATE_KEY")
if not pk:
    raise SystemExit("PRIVATE_KEY env var not set.")

w3 = Web3(Web3.HTTPProvider(RPC_URL))
acct = w3.eth.account.from_key(pk)
c = w3.eth.contract(address=ADDRESS, abi=abi)

print("Contract:", ADDRESS)
print("Caller:  ", acct.address)

# ---- 1. READ: validate Chainlink price (free, no gas) ----
print("\n--- getValidatedPrice() ---")
raw = c.functions.getValidatedPrice().call()
print("Raw price (8 decimals):", raw)
print("BTC/USD: $", raw / 1e8)

# ---- 2. WRITE: record a real hedge ----
MARKET = "BTC reach $67,500 in June"
SHARES = 100

print("\n--- recordHedge() ---")
print("market:", MARKET, "| shares:", SHARES)

nonce = w3.eth.get_transaction_count(acct.address)
tx = c.functions.recordHedge(MARKET, SHARES).build_transaction({
    "chainId": CHAIN_ID,
    "from": acct.address,
    "nonce": nonce,
    "gasPrice": w3.eth.gas_price,
})
est = w3.eth.estimate_gas(tx)
tx["gas"] = int(est * 1.2)
print("Estimated gas:", est)

signed = acct.sign_transaction(tx)
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print("Tx hash:", tx_hash.hex())
print("Waiting for confirmation...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
print("Status:", "SUCCESS" if receipt.status == 1 else "FAILED")
print("Block:", receipt.blockNumber, "| gas used:", receipt.gasUsed)
print("Explorer: https://sepolia.basescan.org/tx/0x" + tx_hash.hex())

# ---- 3. decode the HedgeRecorded event ----
logs = c.events.HedgeRecorded().process_receipt(receipt)
if logs:
    ev = logs[0]["args"]
    print("\n--- HedgeRecorded event ---")
    print("id:", ev["id"])
    print("account:", ev["account"])
    print("market:", ev["market"])
    print("shares:", ev["shares"])
    print("guardPrice (8dp):", ev["guardPrice"], "-> $", ev["guardPrice"] / 1e8)

print("\nTotal hedges on-chain:", c.functions.hedgeCount().call())
