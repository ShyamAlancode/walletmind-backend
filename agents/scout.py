# agents/scout.py
import os, json
import google.generativeai as genai

SCOUT_PROMPT = """You are WalletMind Market Scout Agent — a data harvesting specialist.
Your ONLY job: summarize raw wallet + market data into a compact JSON brief for the Strategy Advisor Agent.

Output STRICT JSON only, no extra text:
{
  "wallet": "0.0.XXXXX",
  "hbar_balance": float,
  "token_count": int,
  "nft_count": int,
  "total_tx_count": int,
  "last_tx_days_ago": int,
  "hbar_price_usd": float,
  "portfolio_usd_value": float,
  "top_tokens": ["list", "of", "token", "symbols"],
  "activity_level": "dormant|low|moderate|active|power_user",
  "defi_exposure": "none|beginner|intermediate|advanced",
  "scout_recommendation": "one sentence on what this wallet needs most"
}"""

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config={"max_output_tokens": 2048, "temperature": 0.1}
)

async def run_scout(wallet_address: str, raw_data: dict) -> dict:
    """Agent 1: Digest raw Mirror Node data into a structured brief."""
    
    prompt_text = f"{SCOUT_PROMPT}\n\nWallet: {wallet_address}\n\nRaw Data:\n{json.dumps(raw_data, indent=2)[:3000]}"
    
    response = await gemini_model.generate_content_async(prompt_text)
    
    # Parse JSON from response
    try:
        content = response.text.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        brief = json.loads(content)
    except Exception:
        brief = {"wallet": wallet_address, "raw_summary": response.text[:500]}
    
    return brief
