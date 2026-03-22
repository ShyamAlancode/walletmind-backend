# create_topics.py
import os
import sys
from dotenv import load_dotenv
load_dotenv()

import hiero_sdk_python as h
from hiero_sdk_python.client.network import Network

def run():
    print("--- WalletMind: HCS Topic Creation (Python SDK) ---")
    
    HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID")
    HEDERA_PRIVATE_KEY = os.getenv("HEDERA_PRIVATE_KEY")
    
    if not HEDERA_ACCOUNT_ID or not HEDERA_PRIVATE_KEY:
        print("❌ Error: Missing HEDERA_ACCOUNT_ID or HEDERA_PRIVATE_KEY")
        return

    client = h.Client(network=Network(network="testnet"))
    try:
        pk = h.PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY.replace("0x", ""))
    except Exception:
        pk = h.PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
    client.set_operator(h.AccountId.from_string(HEDERA_ACCOUNT_ID), pk)

    topics = {}
    names = ["Market Scout", "Strategy Advisor", "Risk Auditor"]
    
    for name in names:
        try:
            print(f"Creating topic: {name}...")
            receipt = h.TopicCreateTransaction().execute(client)
            topic_id = str(receipt.topic_id)
            topics[name] = topic_id
            print(f"✅ {name} Topic: {topic_id}")
        except Exception as e:
            print(f"❌ Failed to create {name} topic: {e}")
            return

    print("\n--- Summary (Copy to .env) ---")
    print(f"HCS_TOPIC_SCOUT={topics['Market Scout']}")
    print(f"HCS_TOPIC_ADVISOR={topics['Strategy Advisor']}")
    print(f"HCS_TOPIC_RISK={topics['Risk Auditor']}")

if __name__ == "__main__":
    run()
