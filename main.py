import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

from mirror_node import get_wallet_data, get_saucerswap_data, get_bonzo_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WalletMind API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEDERA_ACCOUNT_ID = os.getenv("HEDERA_ACCOUNT_ID", "")
HEDERA_PRIVATE_KEY = os.getenv("HEDERA_PRIVATE_KEY", "")
HEDERA_NETWORK = os.getenv("HEDERA_NETWORK", "testnet")


@tool
def fetch_wallet_info(account_id: str) -> str:
    """
    Fetch real-time wallet information for a Hedera account.
    Returns HBAR balance, token holdings, recent transactions, and NFTs.
    Input: Hedera account ID in format 0.0.xxxxxx
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            data = loop.run_until_complete(get_wallet_data(account_id))
            if "error" in data:
                return f"Error fetching wallet: {data['error']}"
            return json.dumps(data, indent=2)
        finally:
            loop.close()
    except Exception as e:
        return f"fetch_wallet_info failed: {str(e)}"


@tool
def fetch_defi_opportunities() -> str:
    """
    Fetch current DeFi opportunities on Hedera including SaucerSwap
    and Bonzo Finance data. Returns yield context and protocol information.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            saucer = loop.run_until_complete(get_saucerswap_data())
            bonzo = loop.run_until_complete(get_bonzo_data())
            return json.dumps({
                "saucerswap": saucer,
                "bonzo_finance": bonzo,
            }, indent=2)
        finally:
            loop.close()
    except Exception as e:
        return f"fetch_defi_opportunities failed: {str(e)}"


@tool
def get_hbar_price() -> str:
    """
    Get current HBAR price and market context from Hedera Mirror Node.
    Returns price information and market data.
    """
    import httpx
    try:
        resp = httpx.get(
            "https://mainnet-public.mirrornode.hedera.com/api/v1/network/exchangerate",
            timeout=8.0
        )
        if resp.status_code == 200:
            data = resp.json()
            cent_equiv = data.get("current_rate", {}).get("cent_equivalent", 0)
            hbar_equiv = data.get("current_rate", {}).get("hbar_equivalent", 1)
            price_usd = (cent_equiv / hbar_equiv) / 100 if hbar_equiv else 0
            return json.dumps({
                "hbar_price_usd": round(price_usd, 6),
                "source": "Hedera Mirror Node Exchange Rate",
                "timestamp": datetime.utcnow().isoformat(),
            })
        return json.dumps({"hbar_price_usd": "unavailable"})
    except Exception as e:
        return f"get_hbar_price failed: {str(e)}"


@tool
def submit_hcs_message(message: str) -> str:
    """Submit a message to WalletMind HCS topic."""
    try:
        from hiero import Client, AccountId, PrivateKey, TopicId, TopicMessageSubmitTransaction
        HCS_TOPIC_ID = os.getenv("HCS_TOPIC_ID", "")
        if not HCS_TOPIC_ID:
            return "HCS topic not configured"
        client = Client.for_testnet()
        pk = PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
        client.set_operator(AccountId.from_string(HEDERA_ACCOUNT_ID), pk)
        topic_id = TopicId.from_string(HCS_TOPIC_ID)
        tx = TopicMessageSubmitTransaction(
            topic_id=topic_id,
            message=message
        ).execute(client)
        receipt = tx.get_receipt(client)
        return f"Logged on Hedera. TX: {str(tx.transaction_id)}"
    except Exception as e:
        logger.error(f"HCS tool error: {e}")
        return f"HCS attempted but failed: {str(e)}"


SYSTEM_PROMPT = """You are WalletMind, an expert autonomous DeFi advisor agent for the Hedera blockchain ecosystem.

You have access to powerful tools to fetch real-time data directly from the Hedera network:
- fetch_wallet_info: Get real wallet holdings from Hedera Mirror Node
- fetch_defi_opportunities: Get live DeFi protocol data from SaucerSwap and Bonzo Finance
- get_hbar_price: Get current HBAR price from Hedera network
- submit_hcs_message: Log interactions immutably to Hedera Consensus Service

AGENT BEHAVIOR:
1. ALWAYS call fetch_wallet_info first with the provided wallet address
2. ALWAYS call fetch_defi_opportunities to get current market context
3. ALWAYS call get_hbar_price for price context
4. Generate a personalized strategy based on the REAL data returned
5. ALWAYS call submit_hcs_message to log the interaction on-chain

RESPONSE FORMAT - plain text only, no markdown:
- Section headers in ALL CAPS
- Numbered lists for recommendations
- Dashed lists for risk factors
- Reference EXACT balances from wallet data
- Never invent yield percentages"""


def create_walletmind_agent():
    llm = ChatGroq(
        api_key=os.getenv("GROQ_API_KEY"),
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=2000,
    )

    tools = [
        fetch_wallet_info,
        fetch_defi_opportunities,
        get_hbar_price,
        submit_hcs_message,
    ]

    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


class AnalyzeRequest(BaseModel):
    wallet_address: str
    question: Optional[str] = "Give me a complete portfolio analysis and DeFi strategy."


class AnalyzeResponse(BaseModel):
    analysis: str
    wallet_data: dict
    tx_hash: Optional[str]
    timestamp: str
    wallet_address: str
    agent_steps: Optional[int] = None


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "WalletMind",
        "version": "2.0.0",
        "agent": "LangChain + Hedera Agent Kit",
        "llm": "Groq Llama 3.3 70B",
        "hedera_sdk": "hiero-sdk-python",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_wallet(req: AnalyzeRequest):
    import re
    wallet = req.wallet_address.strip()
    if not re.match(r'^\d+\.\d+\.\d+$', wallet):
        raise HTTPException(status_code=400, detail="Invalid Hedera address format. Use: 0.0.xxxxxx")

    logger.info(f"Agent analyzing wallet: {wallet}")

    wallet_data = await get_wallet_data(wallet)
    if "error" in wallet_data:
        raise HTTPException(status_code=404, detail=wallet_data["error"])

    try:
        agent = create_walletmind_agent()

        user_input = f"""Analyze this Hedera wallet and provide a complete DeFi strategy:

Wallet Address: {wallet}
User Question: {req.question}

Steps:
1. Call fetch_wallet_info with "{wallet}"
2. Call fetch_defi_opportunities
3. Call get_hbar_price
4. Provide personalized analysis based on real data
5. Call submit_hcs_message with "WalletMind analysis for {wallet} at {datetime.utcnow().isoformat()}"
"""

        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: agent.invoke({"messages": [{"role": "user", "content": user_input}]})
        )

        analysis = result["messages"][-1].content
        steps = len([m for m in result["messages"] if hasattr(m, "tool_calls") and m.tool_calls])

        tx_hash = None
        for m in result["messages"]:
            if getattr(m, "name", None) == "submit_hcs_message":
                tx_hash = m.content
                break

        return AnalyzeResponse(
            analysis=analysis,
            wallet_data=wallet_data,
            tx_hash=tx_hash,
            timestamp=datetime.utcnow().isoformat(),
            wallet_address=wallet,
            agent_steps=steps,
        )

    except Exception as e:
        logger.error(f"Agent error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/wallet/{address}")
async def get_wallet(address: str):
    import re
    if not re.match(r'^\d+\.\d+\.\d+$', address.strip()):
        raise HTTPException(status_code=400, detail="Invalid address format")
    data = await get_wallet_data(address.strip())
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@app.get("/agent/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "fetch_wallet_info", "description": "Fetch real wallet data from Hedera Mirror Node"},
            {"name": "fetch_defi_opportunities", "description": "Get live DeFi data"},
            {"name": "get_hbar_price", "description": "Get current HBAR price from Hedera"},
            {"name": "submit_hcs_message", "description": "Log to Hedera Consensus Service"},
        ],
        "llm": "Groq Llama 3.3 70B",
        "framework": "LangChain + Hedera Agent Kit",
        "hedera_sdk": "hiero-sdk-python v0.1.9",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
