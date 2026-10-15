"""Fetch recent Ethereum blocks over public JSON-RPC.

Pattern reused from chainlens: async aiohttp, one endpoint, no API key.
The goal here is a compact snapshot the LLM can reason about, not a
general-purpose indexer. We only pull the fields the prompt needs.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import aiohttp
import structlog

from chainmind.schemas import BlockSummary, ChainSnapshot

logger = structlog.get_logger(__name__)


class ChainError(RuntimeError):
    """Raised when the RPC endpoint fails or returns invalid data."""


async def _rpc_call(
    session: aiohttp.ClientSession,
    url: str,
    method: str,
    params: list[Any],
) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with session.post(url, json=payload) as resp:
        if resp.status >= 400:
            msg = f"RPC HTTP {resp.status} on {method}"
            raise ChainError(msg)
        data = await resp.json()
    if "error" in data:
        msg = f"RPC error on {method}: {data['error']}"
        raise ChainError(msg)
    return data.get("result")


def _hex_to_int(value: str | None) -> int:
    if not value:
        return 0
    return int(value, 16)


async def fetch_snapshot(rpc_url: str, blocks_to_scan: int) -> ChainSnapshot:
    """Fetch the last N blocks and return a ChainSnapshot.

    Failures on individual blocks are skipped — a single missing block
    does not invalidate the whole snapshot.
    """
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        head_hex = await _rpc_call(session, rpc_url, "eth_blockNumber", [])
        head = _hex_to_int(head_hex)
        logger.info("chain.head", block=head)

        start = max(0, head - blocks_to_scan + 1)
        numbers = list(range(start, head + 1))

        results = await asyncio.gather(
            *[_fetch_block(session, rpc_url, n) for n in numbers],
            return_exceptions=True,
        )

    blocks: list[BlockSummary] = []
    for n, res in zip(numbers, results, strict=True):
        if isinstance(res, BaseException):
            logger.warning("chain.block_failed", number=n, error=str(res))
            continue
        # res is BlockSummary here — the isinstance check above narrowed it.
        blocks.append(res)

    if not blocks:
        msg = "Could not fetch any blocks from the RPC endpoint"
        raise ChainError(msg)

    return ChainSnapshot(
        captured_at=datetime.now(UTC),
        head_block=head,
        blocks=blocks,
    )


async def _fetch_block(
    session: aiohttp.ClientSession,
    url: str,
    number: int,
) -> BlockSummary:
    result = await _rpc_call(session, url, "eth_getBlockByNumber", [hex(number), False])
    if not isinstance(result, dict):
        msg = f"Block {number} not found"
        raise ChainError(msg)

    base_fee_hex = result.get("baseFeePerGas")
    base_fee_gwei = (
        Decimal(_hex_to_int(base_fee_hex)) / Decimal(1_000_000_000) if base_fee_hex else None
    )

    return BlockSummary(
        number=_hex_to_int(result.get("number")),
        timestamp=datetime.fromtimestamp(_hex_to_int(result.get("timestamp")), tz=UTC),
        gas_used=_hex_to_int(result.get("gasUsed")),
        gas_limit=_hex_to_int(result.get("gasLimit")),
        transaction_count=len(result.get("transactions") or []),
        base_fee_gwei=base_fee_gwei,
    )


def snapshot_to_prompt_data(snapshot: ChainSnapshot) -> dict[str, Any]:
    """Convert the snapshot into a compact JSON-friendly dict for the LLM."""
    return {
        "head_block": snapshot.head_block,
        "captured_at": snapshot.captured_at.isoformat(),
        "avg_gas_used": snapshot.avg_gas_used,
        "avg_tx_per_block": round(snapshot.avg_tx_per_block, 2),
        "blocks": [
            {
                "number": b.number,
                "gas_used": b.gas_used,
                "gas_limit": b.gas_limit,
                "gas_utilization_pct": round(b.gas_utilization_pct, 2),
                "transaction_count": b.transaction_count,
                "base_fee_gwei": str(b.base_fee_gwei) if b.base_fee_gwei is not None else None,
            }
            for b in snapshot.blocks
        ],
    }
