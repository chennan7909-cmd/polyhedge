import asyncio
import os
import json
from dynamic_wallet_sdk import (
    DynamicEvmWalletClient,
    ThresholdSignatureScheme,
    DynamicSDKError,
    AuthenticationError,
)

ENV_ID = os.environ["DYNAMIC_ENV_ID"]
API_TOKEN = os.environ["DYNAMIC_API_TOKEN"]
PASSWORD = os.environ["DYNAMIC_WALLET_PASSWORD"]

async def main():
    async with DynamicEvmWalletClient(ENV_ID) as client:
        await client.authenticate_api_token(API_TOKEN)
        print("Authenticated with Dynamic. Creating server wallet...")

        try:
            wallet = await client.create_wallet_account(
                threshold_signature_scheme=ThresholdSignatureScheme.TWO_OF_TWO,
                password=PASSWORD,
            )
        except AuthenticationError:
            raise SystemExit("Auth failed -- check DYNAMIC_API_TOKEN")
        except DynamicSDKError as e:
            raise SystemExit(f"Wallet creation failed: {e}")

        print("\n=== SERVER WALLET CREATED ===")
        print("Address:  ", wallet.account_address)
        print("Wallet ID:", wallet.wallet_id)

        with open("dynamic_wallet.json", "w") as f:
            json.dump({
                "address": wallet.account_address,
                "wallet_id": wallet.wallet_id,
            }, f, indent=2)
        print("\nSaved to dynamic_wallet.json")
        print("\nNEXT: fund this address with Base Sepolia ETH so the agent can pay gas:")
        print("  ", wallet.account_address)
        print("Faucet: https://www.alchemy.com/faucets/base-sepolia")

asyncio.run(main())
