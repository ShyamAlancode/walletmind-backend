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
    if not HEDERA_ACCOUNT_ID or not HEDERA_PRIVATE_KEY:
        logger.warning("Hedera credentials not set — skipping HCS log")
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

        result = subprocess.run(
            ["node", tmp_path],
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
