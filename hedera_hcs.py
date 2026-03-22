import os
import json
import logging
import tempfile
import subprocess
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID", "")
HEDERA_PRIVATE_KEY = os.getenv("HEDERA_PRIVATE_KEY", "")
HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")
FRONTEND_DIR = os.getenv("FRONTEND_DIR", r"D:\hederamind-frontend")


async def log_to_hcs(payload: dict) -> Optional[str]:
    # Try native hiero SDK first
    try:
        import hiero
    except ImportError:
        try:
            import hiero_sdk as hiero
        except ImportError:
            logger.warning("hiero SDK not available - using Node.js fallback")
            return await _node_fallback(payload)
            
    # Native Python SDK Implementation
    if not HEDERA_ACCOUNT_ID or not HEDERA_PRIVATE_KEY:
        logger.warning("Hedera credentials not set — skipping HCS log")
        return None

    try:
        from hiero import Client, AccountId, PrivateKey, TopicId, TopicMessageSubmitTransaction
        client = Client.for_testnet()
        try:
            pk = PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY.replace("0x", ""))
        except Exception:
            pk = PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
        client.set_operator(AccountId.from_string(HEDERA_ACCOUNT_ID), pk)
        topic_id_str = os.getenv("HCS_TOPIC_ID", "")
        if not topic_id_str:
            from hiero import TopicCreateTransaction
            receipt = TopicCreateTransaction().set_topic_memo("WalletMind AI Agent — Hedera Apex Hackathon 2026").execute(client)
            os.environ["HCS_TOPIC_ID"] = str(receipt.topic_id)
            topic_id_str = str(receipt.topic_id)

        topic_id = TopicId.from_string(topic_id_str)
        message_str = json.dumps(payload)
        
        receipt = TopicMessageSubmitTransaction(
            topic_id=topic_id,
            message=message_str[:500]
        ).execute(client)
        tx_id = str(receipt.transaction_id)
        logger.info(f"HCS logged natively: {tx_id}")
        return tx_id
    except Exception as e:
        logger.error(f"Native HCS failed: {e}. Falling back to node.")
        return await _node_fallback(payload)

async def _node_fallback(payload: dict) -> Optional[str]:
    if not HEDERA_ACCOUNT_ID or not HEDERA_PRIVATE_KEY:
        logger.warning("Hedera credentials not set — skipping Node HCS log")
        return None

    try:
        sdk_path = FRONTEND_DIR.replace("\\", "/") + "/node_modules/@hashgraph/sdk"
        script = f"""
const {{ Client, PrivateKey, TopicCreateTransaction, TopicMessageSubmitTransaction }} = require("{sdk_path}");

async function main() {{
    const client = Client.forTestnet();
    client.setRequestTimeout(20000);
    
    const privateKey = PrivateKey.fromStringECDSA("{HEDERA_PRIVATE_KEY.replace('0x', '')}");
    client.setOperator("{HEDERA_ACCOUNT_ID}", privateKey);

    let topicId = "{HCS_TOPIC_ID}";

    if (!topicId) {{
        const createTx = await new TopicCreateTransaction()
            .setTopicMemo("WalletMind AI Agent — Hedera Apex Hackathon 2026")
            .execute(client);
        const receipt = await createTx.getReceipt(client);
        topicId = receipt.topicId.toString();
        console.error("TOPIC:" + topicId);
    }}

    const message = JSON.stringify({json.dumps(payload)});

    const submitTx = await new TopicMessageSubmitTransaction()
        .setTopicId(topicId)
        .setMessage(message)
        .execute(client);

    await submitTx.getReceipt(client);
    console.log(submitTx.transactionId.toString());
    client.close();
    process.exit(0);
}}

main().catch(e => {{ console.error("HCS_ERROR:" + e.message); process.exit(1); }});
"""
        tmp_path = os.path.join(tempfile.gettempdir(), "walletmind_hcs.js")
        with open(tmp_path, "w") as f:
            f.write(script)

        import shutil
        node_path = shutil.which("node") or "/usr/local/bin/node"
        
        result = subprocess.run(
            [node_path, tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=FRONTEND_DIR,
        )

        if result.returncode == 0:
            tx_id = result.stdout.strip()
            logger.info(f"HCS logged: {tx_id}")
            for line in result.stderr.splitlines():
                if line.startswith("TOPIC:"):
                    topic = line.replace("TOPIC:", "").strip()
                    logger.info(f"New HCS topic created: {topic}")
                    os.environ["HCS_TOPIC_ID"] = topic
            return tx_id
        else:
            logger.error(f"HCS failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        logger.error("HCS log timed out")
        return None
    except Exception as e:
        logger.error(f"HCS exception: {e}")
        return None

# Alias for multi-agent orchestrator
submit_hcs_message = log_to_hcs
