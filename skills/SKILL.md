---
name: WalletMind
description: Verifiable AI DeFi advisor for Hedera. Analyzes any Hedera wallet address in real-time and returns personalized portfolio analysis, trading signals, yield opportunities, and risk assessment. Every analysis is permanently logged to Hedera Consensus Service.
version: 1.0.0
author: WalletMind
network: testnet
uaid: hcs://1/0.0.8329089
---

## Overview
WalletMind gives retail users institutional-grade DeFi intelligence on their Hedera wallet. Paste a wallet address, get a personalized 5-section analysis with a DeFi Readiness Score (0-100) and a prioritized Action Queue.

## Capabilities
- `portfolio_analysis` — Fetch real-time HBAR balance, HTS token holdings, NFTs, and last 10 transactions from Hedera Mirror Node
- `defi_readiness_score` — Score 0-100 based on balance size, token diversification, and DeFi activity
- `hcs_logging` — Log every analysis immutably to Hedera Consensus Service, returning a verifiable tx hash
- `scheduled_transactions` — Create Hedera Scheduled Transactions as on-chain strategy commitments
- `defi_opportunities` — Surface live SaucerSwap and Bonzo Finance opportunities relevant to wallet size

## API Endpoints
- `POST /analyze` — `{"wallet_address": "0.0.XXXXXX", "question": "optional"}`
- `GET /health` — Service health check
- `GET /{wallet_address}` — Raw Mirror Node wallet data

## Workflow
1. Call `POST /analyze` with a valid Hedera account ID (format: `0.0.XXXXXX`)
2. Agent fetches wallet data, gets HBAR price, gets DeFi opportunities
3. Logs interaction to HCS topic `0.0.8329089`
4. Creates Scheduled Transaction as strategy intent
5. Returns structured analysis with DeFi Readiness Score + Action Queue

## Constraints
- Only supports Hedera testnet wallet addresses (format `0.0.XXXXXX`)
- Does NOT execute trades — advisory only (non-custodial)
- Does NOT store private keys or wallet credentials
- Requires valid Hedera account ID; rejects invalid formats

## Example
Input: `{"wallet_address": "0.0.8307413", "question": "What yield opportunities do I have?"}`
Output: 5-section analysis with exact HBAR balance, DeFi Readiness Score, and yield-specific Action Queue
