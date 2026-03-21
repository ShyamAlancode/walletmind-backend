import os
import httpx
import logging
from typing import Optional

from datetime import datetime

logger = logging.getLogger(__name__)


async def get_saucerswap_data() -> dict:
    """Fetch real live DeFi data from SaucerSwap public API."""
    urls_to_try = [
        "https://api.saucerswap.finance/stats/platformData",
        "https://api.saucerswap.finance/tokens/",
    ]
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        for url in urls_to_try:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"SaucerSwap data fetched from {url}")
                    
                    if "platformData" in url or "tvl" in str(data):
                        return {
                            "platform_tvl_usd": data.get("tvlUsd", data.get("tvl", "N/A")),
                            "volume_24h_usd": data.get("volume24hUsd", data.get("volume24h", "N/A")),
                            "source": "SaucerSwap Live API",
                            "note": "Use SaucerSwap for HBAR liquidity pools with competitive yields",
                        }
                    
                    if isinstance(data, list) and len(data) > 0:
                        tokens = [
                            {"symbol": t.get("symbol", "?"), "price_usd": t.get("priceUsd", 0)}
                            for t in data[:5]
                        ]
                        return {
                            "top_tokens": tokens,
                            "source": "SaucerSwap Live API",
                            "note": "Live token prices on SaucerSwap DEX",
                        }
            except Exception as e:
                logger.warning(f"SaucerSwap {url} failed: {e}")
                continue
    
    return {
        "source": "SaucerSwap (offline)",
        "note": "SaucerSwap is Hedera's leading DEX offering HBAR liquidity pools with competitive yields typically above simple holding. Bonzo Finance offers lending pools with stablecoin yields in single to low double digits. Both are subject to market conditions.",
        "recommendation": "Visit app.saucerswap.finance for current live rates before making any decisions.",
    }

MIRROR_NODE_URL = os.getenv("MIRROR_NODE_URL", "https://testnet.mirrornode.hedera.com")


async def get_wallet_data(account_id: str) -> dict:
    """Fetch complete wallet data from Hedera Mirror Node."""
    import asyncio
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Account info must be fetched first for immediate validation
        account = await _get_account_info(client, account_id)
        if "error" in account:
            return account

        # Fetch remaining heavy payloads in parallel
        tokens_task = asyncio.create_task(_get_token_balances(client, account_id))
        transactions_task = asyncio.create_task(_get_recent_transactions(client, account_id))
        nfts_task = asyncio.create_task(_get_nft_holdings(client, account_id))
        
        tokens, transactions, nfts = await asyncio.gather(
            tokens_task, transactions_task, nfts_task
        )

    hbar_balance = account.get("balance", {}).get("balance", 0) / 1e8

    return {
        "account_id": account_id,
        "hbar_balance": round(hbar_balance, 4),
        "hbar_balance_raw": account.get("balance", {}).get("balance", 0),
        "evm_address": account.get("evm_address", ""),
        "created_timestamp": account.get("created_timestamp", ""),
        "memo": account.get("memo", ""),
        "tokens": tokens,
        "recent_transactions": transactions,
        "nfts": nfts,
        "token_count": len(tokens),
        "tx_count_30d": len(transactions),
    }


async def _get_account_info(client: httpx.AsyncClient, account_id: str) -> dict:
    try:
        resp = await client.get(f"{MIRROR_NODE_URL}/api/v1/accounts/{account_id}")
        if resp.status_code == 404:
            return {"error": f"Account {account_id} not found on Hedera testnet"}
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Account fetch error: {e}")
        return {"error": f"Failed to fetch account: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Network error: {str(e)}"}


async def _get_token_balances(client: httpx.AsyncClient, account_id: str) -> list:
    try:
        resp = await client.get(
            f"{MIRROR_NODE_URL}/api/v1/accounts/{account_id}/tokens",
            params={"limit": 50, "order": "desc"},
        )
        resp.raise_for_status()
        data = resp.json()
        tokens = []
        for t in data.get("tokens", []):
            token_info = await _get_token_info(client, t.get("token_id", ""))
            balance_raw = t.get("balance", 0)
            decimals = token_info.get("decimals", 0)
            balance = balance_raw / (10 ** int(decimals)) if decimals else balance_raw
            tokens.append({
                "token_id": t.get("token_id"),
                "symbol": token_info.get("symbol", "UNKNOWN"),
                "name": token_info.get("name", "Unknown Token"),
                "balance": round(balance, 6),
                "balance_raw": balance_raw,
                "decimals": decimals,
                "type": token_info.get("type", "FUNGIBLE_COMMON"),
            })
        return tokens
    except Exception as e:
        logger.error(f"Token fetch error: {e}")
        return []


async def _get_token_info(client: httpx.AsyncClient, token_id: str) -> dict:
    if not token_id:
        return {}
    try:
        resp = await client.get(f"{MIRROR_NODE_URL}/api/v1/tokens/{token_id}")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


async def _get_recent_transactions(client: httpx.AsyncClient, account_id: str) -> list:
    try:
        resp = await client.get(
            f"{MIRROR_NODE_URL}/api/v1/transactions",
            params={"account.id": account_id, "limit": 20, "order": "desc"},
        )
        resp.raise_for_status()
        data = resp.json()
        txs = []
        for tx in data.get("transactions", []):
            txs.append({
                "transaction_id": tx.get("transaction_id"),
                "type": tx.get("name"),
                "result": tx.get("result"),
                "consensus_timestamp": tx.get("consensus_timestamp"),
                "transfers": tx.get("transfers", [])[:3],
            })
        return txs
    except Exception as e:
        logger.error(f"Transaction fetch error: {e}")
        return []


async def _get_nft_holdings(client: httpx.AsyncClient, account_id: str) -> list:
    try:
        resp = await client.get(
            f"{MIRROR_NODE_URL}/api/v1/accounts/{account_id}/nfts",
            params={"limit": 20},
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "token_id": nft.get("token_id"),
                "serial_number": nft.get("serial_number"),
                "metadata": nft.get("metadata", ""),
            }
            for nft in data.get("nfts", [])
        ]
    except Exception as e:
        logger.error(f"NFT fetch error: {e}")
        return []


async def get_bonzo_data() -> dict:
    """Fetch Bonzo Finance token data from Hedera Mirror Node."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://testnet.mirrornode.hedera.com/api/v1/tokens/0.0.1183558"
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "protocol": "Bonzo Finance",
                    "token_symbol": data.get("symbol", "BONZO"),
                    "token_name": data.get("name", "Bonzo Finance Token"),
                    "token_id": "0.0.1183558",
                    "total_supply": data.get("total_supply", "N/A"),
                    "decimals": data.get("decimals", 0),
                    "source": "Hedera Mirror Node (live)",
                    "note": "Bonzo Finance is Hedera's leading lending protocol",
                }
    except Exception as e:
        logger.error(f"Bonzo fetch error: {e}")
    return {
        "protocol": "Bonzo Finance",
        "token_id": "0.0.1183558",
        "note": "Leading Hedera lending protocol offering stablecoin yields",
        "source": "fallback",
    }
