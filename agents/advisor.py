# agents/advisor.py
import os, json
from groq import AsyncGroq

ADVISOR_PROMPT = """You are WalletMind Strategy Advisor Agent — a DeFi strategy specialist.
You receive a structured wallet brief from Market Scout Agent (via HCS) and produce a personalized strategy.

Output in this exact format:

DEFI_READINESS_SCORE: [0-100]

PORTFOLIO_DIAGNOSIS:
[2-3 sentences on wallet's current state]

STRATEGY_PLAYBOOK:
1. [Immediate action — specific to this wallet's balance and tokens]
2. [Short-term (1-2 weeks) — specific DeFi move on Hedera]
3. [Long-term (1-3 months) — specific growth strategy]

HEDERA_NATIVE_MOVES:
• SaucerSwap: [specific action or "not applicable — balance too low"]
• Bonzo Finance: [specific lending/borrowing recommendation]
• HBAR Staking: [specific node recommendation with estimated APR]

CAPITAL_ALLOCATION:
• Keep liquid: X%
• Deploy to DeFi: X%
• Stake: X%

ACTION_QUEUE:
→ [Most urgent action with exact HBAR amount if applicable]
→ [Second action]
→ [Third action]"""

async def run_advisor(scout_brief: dict) -> str:
    """Agent 2: Reads Scout's brief (via HCS) and generates DeFi strategy."""
    groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    
    prompt_text = f"Market Scout Agent brief (from HCS):\n\n{json.dumps(scout_brief, indent=2)}"
    
    response = await groq_client.chat.completions.create(
        model="gemma2-9b-it",
        messages=[
            {"role": "system", "content": ADVISOR_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        max_tokens=2048,
        temperature=0.4
    )
    return response.choices[0].message.content
