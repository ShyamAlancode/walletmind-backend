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
import httpx

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── ENV ──────────────────────────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
HEDERA_ACCOUNT_ID  = os.getenv("HEDERA_ACCOUNT_ID", "")
HEDERA_PRIVATE_KEY = os.getenv("HEDERA_PRIVATE_KEY", "")
HCS_TOPIC_ID       = os.getenv("HCS_TOPIC_ID", "")
MIRROR_NODE_URL    = os.getenv("MIRROR_NODE_URL", "https://testnet.mirrornode.hedera.com")

# ── STATS ─────────────────────────────────────────────────────────────────────
_stats = {
    "analyses_run": 0,
    "hcs_messages_logged": 0,
    "scheduled_transactions": 0,
    "wallets_analyzed": set(),
}

# ── FASTAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="WalletMind API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── TOOLS ─────────────────────────────────────────────────────────────────────

@tool
def fetch_wallet_info(wallet_address: str) -> str:
    """Fetch real-time wallet data from Hedera Mirror Node including HBAR balance, tokens, and recent transactions."""
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=15.0) as client:
            acc = client.get(f"{MIRROR_NODE_URL}/api/v1/accounts/{wallet_address}")
            if acc.status_code == 404:
                return json.dumps({"error": f"Wallet {wallet_address} not found on Hedera testnet"})
            acc.raise_for_status()
            acc_data = acc.json()

            hbar_balance = round(acc_data.get("balance", {}).get("balance", 0) / 1e8, 4)

            tok_resp = client.get(f"{MIRROR_NODE_URL}/api/v1/accounts/{wallet_address}/tokens", params={"limit": 10})
            tokens = []
            if tok_resp.status_code == 200:
                for t in tok_resp.json().get("tokens", []):
                    tokens.append({
                        "token_id": t.get("token_id"),
                        "balance": t.get("balance", 0),
                    })

            tx_resp = client.get(
                f"{MIRROR_NODE_URL}/api/v1/transactions",
                params={"account.id": wallet_address, "limit": 5, "order": "desc"},
            )
            txs = []
            if tx_resp.status_code == 200:
                for tx in tx_resp.json().get("transactions", []):
                    txs.append({
                        "id": tx.get("transaction_id"),
                        "type": tx.get("name"),
                        "result": tx.get("result"),
                    })

        return json.dumps({
            "wallet": wallet_address,
            "hbar_balance": hbar_balance,
            "tokens": tokens,
            "recent_transactions": txs,
            "evm_address": acc_data.get("evm_address", ""),
        })
    except Exception as e:
        logger.error(f"fetch_wallet_info error: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_hbar_price() -> str:
    """Get the current real-time HBAR/USD exchange rate from Hedera Mirror Node."""
    try:
        import httpx as _httpx
        with _httpx.Client(timeout=10.0) as client:
            resp = client.get("https://mainnet-public.mirrornode.hedera.com/api/v1/network/exchangerate")
            resp.raise_for_status()
            data = resp.json()
            cents = data.get("current_rate", {}).get("cent_equivalent", 0)
            hbar_eq = data.get("current_rate", {}).get("hbar_equivalent", 1)
            usd = round((cents / 100) / hbar_eq, 6) if hbar_eq else 0
            return json.dumps({"hbar_usd": usd, "source": "Hedera Mirror Node"})
    except Exception as e:
        logger.error(f"get_hbar_price error: {e}")
        return json.dumps({"hbar_usd": 0.065, "source": "fallback", "error": str(e)})


@tool
def get_defi_opportunities() -> str:
    """Get live DeFi opportunities on Hedera including Bonzo Finance lending rates."""
    try:
        import httpx as _httpx
        bonzo = {}
        with _httpx.Client(timeout=8.0) as client:
            # 1. Try Bonzo's live pool API
            try:
                resp = client.get("https://app.bonzo.finance/api/pools", timeout=5.0)
                if resp.status_code == 200:
                    bonzo = {"protocol": "Bonzo Finance", "data": resp.json(), "source": "live"}
            except Exception:
                pass

            # 2. Fallback: Mirror Node token data if live pools fail
            if not bonzo:
                resp = client.get(f"{MIRROR_NODE_URL}/api/v1/tokens/0.0.1183558")
                if resp.status_code == 200:
                    d = resp.json()
                    bonzo = {
                        "protocol": "Bonzo Finance",
                        "token": d.get("symbol", "BONZO"),
                        "hbar_supply_apy": "~3-5% (check app.bonzo.finance for live rate)",
                        "source": "Hedera Mirror Node token fallback",
                    }

        return json.dumps({
            "bonzo_finance": bonzo or {"protocol": "Bonzo Finance", "note": "Leading Hedera lending protocol"},
            "saucerswap": {
                "protocol": "SaucerSwap",
                "note": "Hedera's leading DEX — HBAR liquidity pools with competitive yields",
                "url": "https://app.saucerswap.finance",
            },
            "heliswap": {
                "protocol": "HeliSwap",
                "note": "Hedera DEX supporting HTS tokens",
                "url": "https://heliswap.io",
            },
            "disclaimer": "Visit each protocol for live APR rates. Yields vary with market conditions.",
        })
    except Exception as e:
        logger.error(f"get_defi_opportunities error: {e}")
        return json.dumps({"error": str(e)})


@tool
def submit_hcs_message(wallet_address: str, action: str, summary: str) -> str:
    """Log a portfolio analysis event permanently to the Hedera Consensus Service (HCS) for immutable on-chain record."""
    try:
        import hiero_sdk_python as h
        from hiero_sdk_python.client.network import Network

        client = h.Client(network=Network(network="testnet"))
        try:
            pk = h.PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY.replace("0x", ""))
        except Exception:
            pk = h.PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
        client.set_operator(h.AccountId.from_string(HEDERA_ACCOUNT_ID), pk)

        payload = json.dumps({
            "service": "WalletMind",
            "version": "2.0.0",
            "wallet": wallet_address,
            "action": action,
            "summary": summary[:200],
            "timestamp": datetime.utcnow().isoformat(),
        })

        receipt = (
            h.TopicMessageSubmitTransaction()
            .set_topic_id(h.TopicId.from_string(HCS_TOPIC_ID))
            .set_message(payload)
            .execute(client)
        )
        tx_id = str(receipt.transaction_id)
        _stats["hcs_messages_logged"] += 1
        logger.info(f"HCS logged: {tx_id}")
        return json.dumps({
            "success": True,
            "transaction_id": tx_id,
            "topic": HCS_TOPIC_ID,
            "hashscan_url": f"https://hashscan.io/testnet/transaction/{tx_id}",
        })
    except Exception as e:
        logger.error(f"HCS failed: {e}")
        return json.dumps({"success": False, "error": str(e)})


@tool
def create_scheduled_transaction(strategy_memo: str) -> str:
    """Create a Hedera Scheduled Transaction as on-chain proof of a recommended DeFi strategy execution intent."""
    try:
        import hiero_sdk_python as h
        from hiero_sdk_python.client.network import Network

        client = h.Client(network=Network(network="testnet"))
        op_id = h.AccountId.from_string(HEDERA_ACCOUNT_ID)
        try:
            pk = h.PrivateKey.from_string_ecdsa(HEDERA_PRIVATE_KEY.replace("0x", ""))
        except Exception:
            pk = h.PrivateKey.from_string(HEDERA_PRIVATE_KEY.replace("0x", ""))
        client.set_operator(op_id, pk)

        transfer = (
            h.TransferTransaction()
            .add_hbar_transfer(op_id, -1000000)
            .add_hbar_transfer(op_id, 1000000)
        )
        receipt = (
            h.ScheduleCreateTransaction()
            .set_scheduled_transaction(transfer)
            .set_schedule_memo(f"WalletMind: {strategy_memo[:60]}")
            .execute(client)
        )
        schedule_id = str(receipt.schedule_id)
        _stats["scheduled_transactions"] += 1
        logger.info(f"Scheduled tx: {schedule_id}")
        return json.dumps({
            "success": True,
            "schedule_id": schedule_id,
            "hashscan_url": f"https://hashscan.io/testnet/schedule/{schedule_id}",
        })
    except Exception as e:
        logger.error(f"Scheduled tx failed: {e}")
        return json.dumps({"success": False, "error": str(e)})


# ── AGENT ─────────────────────────────────────────────────────────────────────

TOOLS = [fetch_wallet_info, get_hbar_price, get_defi_opportunities,
         submit_hcs_message, create_scheduled_transaction]

SYSTEM_PROMPT = """You are WalletMind, an expert DeFi advisor for Hedera. You give INSTITUTION-GRADE analysis.

TOOL SEQUENCE — call each EXACTLY ONCE in this order:
1. fetch_wallet_info
2. get_hbar_price
3. get_defi_opportunities
4. submit_hcs_message (action="PORTFOLIO_ANALYSIS", summary=first 100 chars of your planned advice)
5. create_scheduled_transaction (strategy_memo=your top recommendation in 10 words)
6. STOP. Write final answer immediately. Do NOT call any tool again.

After all 5 tools, write this EXACT structure using the real data:

## Portfolio Summary
You hold [EXACT HBAR from fetch_wallet_info] ℏ worth approximately $[calculate: balance × hbar_usd from get_hbar_price] USD. [1 sentence on overall composition].

## Trading & Staking Analysis
- Trading activity: [describe recent tx types from fetch_wallet_info — CRYPTOTRANSFER, SCHEDULECREATE etc]
- Staking exposure: [does wallet show staking activity? if no tokens, say so explicitly]
- Current position: [idle HBAR vs active DeFi — be specific]

## Yield Opportunities
- [Protocol 1 from get_defi_opportunities]: [specific opportunity for THIS wallet size]
- [Protocol 2]: [specific opportunity]
- Suggested allocation: [e.g. "30% of idle HBAR into SaucerSwap HBAR/USDC pool"]

## Risk Assessment
- Market risk: [HBAR price volatility impact on this specific balance]
- Concentration risk: [% of portfolio in single asset]
- Protocol risk: [if entering DeFi, what to watch]
- Overall: LOW / MEDIUM / HIGH with one sentence why

## DeFi Readiness Score
Score: [0-100]/100 — [Label: Beginner / Developing / Active / Advanced]
Scoring:
- HBAR balance sufficient for DeFi (>100 HBAR = +30 pts): [pts]
- Token diversification (each token = +10 pts, max 30): [pts]  
- Recent DeFi activity (SCHEDULECREATE/CONSENSUSSUBMIT = +10 pts each, max 40): [pts]
Total: [sum]/100
Verdict: [1 sentence on what to do based on score]

## Action Queue
1. [Verb] [specific action with protocol name and amount] — Priority: HIGH/MEDIUM/LOW
2. [Verb] [specific action] — Priority: HIGH/MEDIUM/LOW  
3. [Verb] [specific action] — Priority: HIGH/MEDIUM/LOW
4. [Verb] [specific action] — Priority: LOW

RULES:
- Use EXACT numbers from tool outputs. Never invent values.
- Never invent APY percentages. Reference protocols qualitatively.
- Answer the user's specific question if they asked one.
- If question is just "analyze" — give the full structure above.
"""

from agents.orchestrator import run_agent_network

# ── MODELS ────────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    wallet_address: str
    question: Optional[str] = "Give me a complete portfolio analysis and DeFi strategy."

class AnalyzeResponse(BaseModel):
    analysis: str
    wallet_data: dict = {}
    agent_events: list = []
    scout_brief: dict = {}
    advisor_strategy: str = ""
    risk_report: str = ""
    verdict: str = ""
    tx_hash: Optional[str] = None
    schedule_id: Optional[str] = None
    hashscan_url: Optional[str] = None
    hcs_topic: Optional[str] = None
    hcs_transactions: dict = {}
    timestamp: str
    wallet_address: str

# ── CALLBACKS ─────────────────────────────────────────────────────────────────
class ToolOutputCapture(BaseCallbackHandler):
    """Captures tool outputs even if agent crashes before returning."""
    def __init__(self):
        self.tool_outputs = []
    def on_tool_end(self, output, **kwargs):
        if isinstance(output, str):
            self.tool_outputs.append(output)

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"service": "WalletMind API", "status": "ok", "version": "2.0.0"}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "WalletMind",
        "version": "2.0.0",
        "agent": "LangChain + Hedera Agent Kit",
        "hcs_topic": HCS_TOPIC_ID,
    }

@app.get("/stats")
async def get_stats():
    return {
        "analyses_run": _stats["analyses_run"],
        "hcs_messages_logged": _stats["hcs_messages_logged"],
        "scheduled_transactions": _stats["scheduled_transactions"],
        "unique_wallets": len(_stats["wallets_analyzed"]),
    }

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_wallet(req: AnalyzeRequest):
    wallet = req.wallet_address.strip()
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address required")

    import re
    if not re.match(r"^0\.0\.\d+$", wallet):
        raise HTTPException(status_code=400, detail="Invalid format. Use Hedera format: 0.0.xxxxxx")

    _stats["analyses_run"] += 1
    _stats["wallets_analyzed"].add(wallet)
    logger.info(f"Analyzing wallet: {wallet}")

    # Fetch wallet data for sidebar (parallel to agent)
    wallet_data = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            acc_resp = await client.get(f"{MIRROR_NODE_URL}/api/v1/accounts/{wallet}")
            if acc_resp.status_code == 200:
                acc = acc_resp.json()
                hbar_balance = round(acc.get("balance", {}).get("balance", 0) / 1e8, 4)
                tok_resp = await client.get(
                    f"{MIRROR_NODE_URL}/api/v1/accounts/{wallet}/tokens",
                    params={"limit": 10},
                )
                tokens = tok_resp.json().get("tokens", []) if tok_resp.status_code == 200 else []
                wallet_data = {
                    "account_id": wallet,
                    "hbar_balance": hbar_balance,
                    "tokens": tokens,
                    "token_count": len(tokens),
                    "evm_address": acc.get("evm_address", ""),
                }
    except Exception as e:
        logger.warning(f"Sidebar wallet fetch failed: {e}")

    # Run the 3-agent network
    try:
        result = await run_agent_network(wallet, wallet_data)
        
        # Merge individual agent data for the response
        agent_events = result.get("agent_events", [])
        scout_brief = result.get("scout_brief", {})
        advisor_strategy = result.get("advisor_strategy", "")
        risk_report = result.get("risk_report", "")
        verdict = result.get("verdict", "")
        hcs_topic = result.get("hcs_topic")
        hcs_txs = result.get("hcs_transactions", {})
        
        # Compatibility: main analysis string is the Advisor's strategy
        analysis = advisor_strategy or "## Analysis Pending\nAgent network is processing."

        logger.info(f"Agent network complete for {wallet}. Verdict: {verdict}")

        return AnalyzeResponse(
            analysis=analysis,
            wallet_data=wallet_data,
            agent_events=agent_events,
            scout_brief=scout_brief,
            advisor_strategy=advisor_strategy,
            risk_report=risk_report,
            verdict=verdict,
            tx_hash=hcs_txs.get("scout"), # Use scout tx as primary audit ref
            hcs_topic=hcs_topic,
            hcs_transactions=hcs_txs,
            timestamp=datetime.utcnow().isoformat(),
            wallet_address=wallet,
        )

    except Exception as agent_err:
        logger.error(f"Agent Network error: {agent_err}")
        return AnalyzeResponse(
            analysis=f"## System Error\n{str(agent_err)}",
            wallet_address=wallet,
            timestamp=datetime.utcnow().isoformat(),
        )

@app.get("/{wallet_address}")
async def get_wallet(wallet_address: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{MIRROR_NODE_URL}/api/v1/accounts/{wallet_address.strip()}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail="Wallet not found")
        resp.raise_for_status()
        return resp.json()
