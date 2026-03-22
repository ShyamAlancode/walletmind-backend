# agents/orchestrator.py
import os, json, time
from .scout import run_scout
from .advisor import run_advisor
from .risk_auditor import run_risk_auditor
from hedera_hcs import submit_hcs_message  # use existing function

async def run_agent_network(wallet_address: str, raw_wallet_data: dict) -> dict:
    """
    Orchestrates the 3-agent network:
    Scout → HCS Hub → Advisor → HCS Hub → Risk Auditor → HCS Hub
    """
    
    events = []  # Live feed for frontend
    topic_id = os.getenv("HCS_TOPIC_ID")
    
    # ─── AGENT 1: MARKET SCOUT ─────────────────────────────────────
    events.append({"agent": "Market Scout", "status": "running", "message": "Harvesting wallet data from Hedera Mirror Node..."})
    
    scout_brief = await run_scout(wallet_address, raw_wallet_data)
    
    # Scout logs its brief to HCS Hub
    scout_payload = {
        "agent": "WalletMind Market Scout v1",
        "wallet": wallet_address,
        "timestamp": int(time.time()),
        "brief": scout_brief
    }
    scout_tx = await submit_hcs_message(json.dumps(scout_payload))
    
    events.append({
        "agent": "Market Scout",
        "status": "done",
        "message": f"Brief posted to HCS. Portfolio: ${scout_brief.get('portfolio_usd_value', 0):.2f}",
        "hcs_tx": scout_tx,
        "topic": topic_id,
        "data": scout_brief
    })
    
    # ─── AGENT 2: STRATEGY ADVISOR ─────────────────────────────────
    events.append({"agent": "Strategy Advisor", "status": "running", "message": "Reading Scout's brief from HCS. Generating DeFi strategy..."})
    
    advisor_strategy = await run_advisor(scout_brief)
    
    # Advisor logs its strategy to HCS Hub
    advisor_payload = {
        "agent": "WalletMind Strategy Advisor v1",
        "wallet": wallet_address,
        "timestamp": int(time.time()),
        "strategy_summary": advisor_strategy[:500]
    }
    advisor_tx = await submit_hcs_message(json.dumps(advisor_payload))
    
    events.append({
        "agent": "Strategy Advisor",
        "status": "done",
        "message": "Strategy posted to HCS.",
        "hcs_tx": advisor_tx,
        "topic": topic_id,
        "data": advisor_strategy
    })
    
    # ─── AGENT 3: RISK AUDITOR ─────────────────────────────────────
    events.append({"agent": "Risk Auditor", "status": "running", "message": "Running independent risk audit on Advisor strategy..."})
    
    risk_report = await run_risk_auditor(scout_brief, advisor_strategy)
    
    # Extract verdict for quick display
    verdict = "CAUTION ⚠️"
    if "SAFE ✅" in risk_report:
        verdict = "SAFE ✅"
    elif "HIGH RISK 🚨" in risk_report:
        verdict = "HIGH RISK 🚨"
    
    # Risk Auditor logs verdict to HCS Hub
    risk_payload = {
        "agent": "WalletMind Risk Auditor v1",
        "wallet": wallet_address,
        "timestamp": int(time.time()),
        "verdict": verdict,
        "risk_summary": risk_report[:500]
    }
    risk_tx = await submit_hcs_message(json.dumps(risk_payload))
    
    events.append({
        "agent": "Risk Auditor",
        "status": "done",
        "message": f"Audit complete. Verdict: {verdict}",
        "hcs_tx": risk_tx,
        "topic": topic_id,
        "data": risk_report,
        "verdict": verdict
    })
    
    return {
        "wallet_address": wallet_address,
        "agent_events": events,
        "scout_brief": scout_brief,
        "advisor_strategy": advisor_strategy,
        "risk_report": risk_report,
        "verdict": verdict,
        "hcs_topic": topic_id,
        "hcs_transactions": {
            "scout": scout_tx,
            "advisor": advisor_tx,
            "risk": risk_tx
        }
    }
