import os
import json
from dotenv import load_dotenv
load_dotenv()

import hiero_sdk_python as h
from hiero_sdk_python.client.network import Network

HEDERA_ACCOUNT_ID  = os.getenv("HEDERA_ACCOUNT_ID")
HEDERA_PRIVATE_KEY = os.getenv("HEDERA_PRIVATE_KEY")

def register():
    print("--- WalletMind: HOL Registry Deployment ---")
    print(f"Using Operator: {HEDERA_ACCOUNT_ID}")

    client = h.Client(network=Network(network="testnet"))
    try:
        pk = h.PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY.replace("0x", ""))
    except Exception:
        pk = h.PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
    client.set_operator(h.AccountId.from_string(HEDERA_ACCOUNT_ID), pk)

    print("\n[1/2] Creating HOL registry topic...")

    # Try without memo first — most reliable
    receipt = (
        h.TopicCreateTransaction()
        .execute(client)
    )
    topic_id = str(receipt.topic_id)
    print(f"Topic created: {topic_id}")

    print("\n[2/2] Publishing agent profile to topic...")
    profile = json.dumps({
        "p": "hcs-10",
        "op": "register",
        "name": "WalletMind",
        "version": "1.0.0",
        "description": "Verifiable AI DeFi copilot for Hedera wallets. Personalized trading, staking, yield, and risk insights with every analysis logged immutably on HCS.",
        "url": "https://walletmind-frontend.vercel.app",
        "capabilities": ["portfolio_analysis", "defi_readiness_score", "hcs_logging", "scheduled_transactions"],
        "network": "testnet",
        "account_id": HEDERA_ACCOUNT_ID
    })

    h.TopicMessageSubmitTransaction()\
        .set_topic_id(h.TopicId.from_string(topic_id))\
        .set_message(profile)\
        .execute(client)

    print(f"\n✅ HOL REGISTRATION COMPLETE")
    print(f"UAID: hcs://1/{topic_id}")
    print(f"HashScan: https://hashscan.io/testnet/topic/{topic_id}")
    print(f"\nAdd to README: **HOL UAID:** hcs://1/{topic_id}")

if __name__ == "__main__":
    register()
