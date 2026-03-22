# agents/risk_auditor.py
import os, json
from langchain_groq import ChatGroq
from langchain.schema import SystemMessage, HumanMessage

RISK_PROMPT = """You are WalletMind Risk Auditor Agent — a completely INDEPENDENT risk analyst.
You receive the Strategy Advisor Agent's recommendations (from HCS) and stress-test them.
You have NO loyalty to the Advisor's strategy. Your job is to protect the user.

Output in this exact format:

RISK_SCORE: [0-100]  ← (0=no risk, 100=liquidation risk)
VERDICT: [SAFE ✅ | CAUTION ⚠️ | HIGH RISK 🚨]

RISK_BREAKDOWN:
• Smart Contract Risk: [LOW/MEDIUM/HIGH] — [1 sentence reason]
• Liquidity Risk: [LOW/MEDIUM/HIGH] — [1 sentence reason]  
• Concentration Risk: [LOW/MEDIUM/HIGH] — [1 sentence reason]
• Market Risk: [LOW/MEDIUM/HIGH] — [1 sentence reason]

ADVISOR_STRATEGY_AUDIT:
[Critique each point in the Advisor's strategy — what could go wrong]

SAFE_THRESHOLDS:
• Maximum DeFi deployment: [X% of portfolio, X HBAR max]
• Emergency exit trigger: [specific condition]
• Stop-loss level: [specific price/condition]

AUDITOR_OVERRIDE:
[If you disagree with the Advisor, state what you would do differently and why]

FINAL_RECOMMENDATION:
[1 clear sentence: proceed / proceed with caution / do not proceed]"""

risk_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2
)

async def run_risk_auditor(scout_brief: dict, advisor_strategy: str) -> str:
    """Agent 3: Reads Advisor's strategy (via HCS) and independently audits risk."""
    
    messages = [
        SystemMessage(content=RISK_PROMPT),
        HumanMessage(content=f"""
Wallet Brief (from Scout Agent via HCS):
{json.dumps(scout_brief, indent=2)}

Strategy Advisor's Recommendations (from HCS Topic B):
{advisor_strategy}

Perform your independent risk audit now.
""")
    ]
    
    response = await risk_llm.ainvoke(messages)
    return response.content
