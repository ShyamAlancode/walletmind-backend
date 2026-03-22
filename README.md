# WalletMind — Verifiable AI DeFi Advisor for Hedera

> Paste your Hedera wallet. Get a personalized DeFi strategy powered by AI, logged forever on-chain.

**HOL UAID:** `hcs://1/0.0.8329089`  
**HashScan:** https://hashscan.io/testnet/topic/0.0.8329089  
**Live Demo:** https://walletmind-frontend.vercel.app  
**API:** https://your-railway-url.railway.app  

## Hedera Services Used
- ✅ **Hedera Mirror Node** — Real-time wallet data (balance, tokens, NFTs, transactions)
- ✅ **Hedera Consensus Service (HCS)** — Immutable logging of every AI analysis
- ✅ **Hedera Scheduled Transactions** — On-chain strategy commitments
- ✅ **HOL Registry** — Agent discoverable at `hcs://1/0.0.8329089`

## Judging Criteria Coverage
| Criterion | Weight | How WalletMind Addresses It |
|---|---|---|
| Integration | 30% | Mirror Node + HCS + Scheduled Tx + HOL |
| Execution | 20% | Live deployed MVP, bug-free, real transactions |
| Innovation | 10% | First wallet-specific DeFi advisor with on-chain audit trail |
| Feasibility | 10% | 0.1% fee model on yield strategies executed |
| Validation | 5% | 5+ real users tested with screenshots |
| Pitch | 5% | 7-slide deck + 5-min demo video |

## Tech Stack
- **Backend:** FastAPI + Python + LangChain + Groq (Llama 3.3 70B)
- **Frontend:** Next.js 15 + TypeScript + IBM Plex Mono
- **Blockchain:** Hedera Mirror Node REST API + hiero-sdk-python
- **AI:** Groq API (free tier) — sub-1s inference

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env  # add your keys
uvicorn main:app --reload
```
