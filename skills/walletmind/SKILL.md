# WalletMind

## Description
Autonomous AI-powered DeFi advisor for Hedera wallets. Analyzes real on-chain holdings, generates personalized trading, staking, yield, and risk strategies, and logs every interaction immutably to Hedera Consensus Service.

## Capabilities
- fetch_wallet_info: Retrieves HBAR balance, token holdings, transaction history from Hedera Mirror Node
- get_hbar_price: Fetches real-time HBAR/USD exchange rate
- get_defi_opportunities: Returns live Hedera DeFi protocol context (SaucerSwap, Bonzo Finance, HeliSwap)
- submit_hcs_message: Logs every analysis permanently to Hedera HCS
- create_scheduled_transaction: Creates on-chain proof of recommended strategy intent

## Input
Hedera wallet address (format: 0.0.xxxxxx) + optional natural language question

## Output
- DeFi Readiness Score (0-100)
- Trading, staking, yield, and risk analysis
- Numbered action queue with protocol recommendations
- Immutable HCS transaction hash as on-chain proof
- Scheduled transaction ID as strategy intent proof

## Networks
Hedera Testnet (live), Hedera Mainnet (ready)

## Live Demo
https://walletmind-frontend.vercel.app
