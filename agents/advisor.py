# agents/advisor.py
import os, json
import google.generativeai as genai

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

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={"max_output_tokens": 2048, "temperature": 0.4}
)

async def run_advisor(scout_brief: dict) -> str:
    """Agent 2: Reads Scout's brief (via HCS) and generates DeFi strategy."""
    
    prompt_text = f"{ADVISOR_PROMPT}\n\nMarket Scout Agent brief (from HCS):\n\n{json.dumps(scout_brief, indent=2)}"
    
    response = await gemini_model.generate_content_async(prompt_text)
    return response.text
