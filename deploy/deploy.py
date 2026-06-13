import os
import json
from web3 import Web3
from solcx import compile_standard, install_solc, set_solc_version

RPC_URL  = "https://sepolia.base.org"
CHAIN_ID = 84532
PRICE_FEED = Web3.to_checksum_address("0x0FB99723Aee6f420beAD13e6bBB79b7E6F034298")
SOLC_VERSION = "0.8.19"
CONTRACT_FILE = "HedgeGuard.sol"
CONTRACT_NAME = "HedgeGuard"

pk = os.environ.get("PRIVATE_KEY")
if not pk:
    raise SystemExit("PRIVATE_KEY env var not set. Run: export PRIVATE_KEY=\"0x...\"")

print("Installing solc", SOLC_VERSION, "...")
install_solc(SOLC_VERSION)
set_solc_version(SOLC_VERSION)

with open(CONTRACT_FILE, "r") as f:
    source = f.read()

print("Compiling", CONTRACT_FILE, "...")
compiled = compile_standard(
    {
        "language": "Solidity",
        "sources": {CONTRACT_FILE: {"content": source}},
        "settings": {
            "optimizer": {"enabled": True, "runs": 200},
            "outputSelection": {"*": {"*": ["abi", "evm.bytecode.object"]}},
        },
    },
    solc_version=SOLC_VERSION,
)

contract_data = compiled["contracts"][CONTRACT_FILE][CONTRACT_NAME]
abi = contract_data["abi"]
bytecode = contract_data["evm"]["bytecode"]["object"]

with open("HedgeGuard_abi.json", "w") as f:
    json.dump(abi, f, indent=2)

w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise SystemExit("Cannot connect to RPC " + RPC_URL)

acct = w3.eth.account.from_key(pk)
print("Deployer:", acct.address)

bal = w3.eth.get_balance(acct.address)
print("Balance:", w3.from_wei(bal, "ether"), "ETH")
if bal == 0:
    raise SystemExit("Balance is 0. Fund the wallet on Base Sepolia first.")

HedgeGuard = w3.eth.contract(abi=abi, bytecode=bytecode)

nonce = w3.eth.get_transaction_count(acct.address)
tx = HedgeGuard.constructor(PRICE_FEED).build_transaction({
    "chainId": CHAIN_ID,
    "from": acct.address,
    "nonce": nonce,
    "gasPrice": w3.eth.gas_price,
})

try:
    est = w3.eth.estimate_gas(tx)
    tx["gas"] = int(est * 1.2)
    print("Estimated gas:", est, "-> using", tx["gas"])
except Exception as e:
    tx["gas"] = 1_500_000
    print("Gas estimate failed (", e, "); using fallback 1,500,000")

signed = acct.sign_transaction(tx)
print("Sending deployment transaction...")
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
print("Tx hash:", tx_hash.hex())
print("Waiting for confirmation...")

receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
print("\n=== DEPLOYED ===")
print("Contract address:", receipt.contractAddress)
print("Block:", receipt.blockNumber)
print("Gas used:", receipt.gasUsed)
print("Explorer: https://sepolia.basescan.org/address/" + receipt.contractAddress)

with open("deployment.json", "w") as f:
    json.dump({
        "address": receipt.contractAddress,
        "tx_hash": tx_hash.hex(),
        "deployer": acct.address,
        "price_feed": PRICE_FEED,
    }, f, indent=2)
print("\nSaved address + abi to deployment.json / HedgeGuard_abi.json")
