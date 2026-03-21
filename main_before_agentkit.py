import os
import json
import logging
from datetime import datetime
import asyncio
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from groq import Groq

from mirror_node import get_wallet_data, get_saucerswap_data
from hedera_hcs import log_to_hcs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_bonzo_data() -> dict:
    """Fetch real Bonzo Finance lending data."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://mainnet-public.mirrornode.hedera.com/api/v1/tokens/0.0.1646100"
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "protocol": "Bonzo Finance",
                    "token": data.get("symbol", "BONZO"),
                    "name": data.get("name", "Bonzo Finance Token"),
                    "total_supply": data.get("total_supply", "N/A"),
                    "source": "Hedera Mirror Node (live)",
                }
    except Exception as e:
        logger.error(f"Bonzo fetch error: {e}")
    return {
        "protocol": "Bonzo Finance",
        "note": "Leading Hedera lending protocol",
        "source": "fallback",
    }

app = FastAPI(title="WalletMind API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are WalletMind, an expert DeFi advisor for the Hedera blockchain ecosystem.

You have access to real-time wallet data AND live SaucerSwap pool data including actual APR percentages and TVL.

Your role:
- Analyze the user's specific portfolio with precision
- Give concrete, actionable DeFi strategies using the REAL APR data provided
- Reference actual token amounts and the specific pool APRs from SaucerSwap data
- Explain yield opportunities on Hedera (SaucerSwap, Bonzo Finance)
- Assess risk levels clearly
- Be direct, confident, and specific

FORMATTING RULES — CRITICAL:
- Use plain text only
- No markdown symbols like ##, **, or --
- Use numbered lists: 1. 2. 3.
- Use dashed lists: - item
- Use ALL CAPS for section headers like: PORTFOLIO SUMMARY, KEY OBSERVATIONS, RECOMMENDED STRATEGY, RISK ASSESSMENT
- Never invent APR numbers — only use the real data provided

Always reference the user's actual token balances and real SaucerSwap APRs."""


class AnalyzeRequest(BaseModel):
    wallet_address: str
    question: Optional[str] = "Give me a complete portfolio analysis and strategy."


class AnalyzeResponse(BaseModel):
    analysis: str
    wallet_data: dict
    tx_hash: Optional[str]
    timestamp: str
    wallet_address: str


@app.get("/health")
async def health():
    return {"status": "ok", "service": "WalletMind", "version": "1.0.0"}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_wallet(req: AnalyzeRequest):
    wallet = req.wallet_address.strip()
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address required")

    logger.info(f"Analyzing wallet: {wallet}")

    wallet_data = await get_wallet_data(wallet)
    defi_data = await get_saucerswap_data()

    bonzo_data = await get_bonzo_data()

    if not wallet_data or "error" in wallet_data:
        raise HTTPException(status_code=404, detail=wallet_data.get("error", "Wallet not found"))

    wallet_context = json.dumps(wallet_data, indent=2)
    defi_context = json.dumps(defi_data, indent=2)

    user_message = f"""
Wallet Address: {wallet}

Current Portfolio Data:
{wallet_context}

Live SaucerSwap DeFi Data (real-time):
{defi_context}

Live Bonzo Finance Data:
{json.dumps(bonzo_data, indent=2)}

User Question: {req.question}

Please provide a detailed, personalized analysis based on these exact holdings and the live DeFi data above. Reference specific pool APRs and TVL from the SaucerSwap data when making recommendations.
"""

    message = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1500,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    analysis = message.choices[0].message.content

    hcs_result = await log_to_hcs({
        "wallet": wallet,
        "timestamp": datetime.utcnow().isoformat(),
        "question": req.question,
        "tokens_analyzed": len(wallet_data.get("tokens", [])),
        "hbar_balance": wallet_data.get("hbar_balance", 0),
    })
    tx_hash = hcs_result

    return AnalyzeResponse(
        analysis=analysis,
        wallet_data=wallet_data,
        tx_hash=tx_hash,
        timestamp=datetime.utcnow().isoformat(),
        wallet_address=wallet,
    )


@app.get("/wallet/{address}")
async def get_wallet(address: str):
    data = await get_wallet_data(address.strip())
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
