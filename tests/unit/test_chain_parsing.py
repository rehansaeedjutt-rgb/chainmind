"""Tests for chain reader helpers. No network calls."""

from datetime import UTC, datetime
from decimal import Decimal

from chainmind.chain.reader import _hex_to_int, snapshot_to_prompt_data
from chainmind.schemas import BlockSummary, ChainSnapshot


def test_hex_to_int_basic() -> None:
    assert _hex_to_int("0x10") == 16
    assert _hex_to_int("0x0") == 0


def test_hex_to_int_none_and_empty() -> None:
    assert _hex_to_int(None) == 0
    assert _hex_to_int("") == 0


def _snapshot() -> ChainSnapshot:
    return ChainSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        head_block=100,
        blocks=[
            BlockSummary(
                number=99,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                gas_used=10_000_000,
                gas_limit=30_000_000,
                transaction_count=100,
                base_fee_gwei=Decimal("5.0"),
            ),
            BlockSummary(
                number=100,
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                gas_used=20_000_000,
                gas_limit=30_000_000,
                transaction_count=200,
                base_fee_gwei=None,
            ),
        ],
    )


def test_snapshot_to_prompt_shape() -> None:
    data = snapshot_to_prompt_data(_snapshot())
    assert data["head_block"] == 100
    assert data["avg_gas_used"] == 15_000_000
    assert data["avg_tx_per_block"] == 150.0
    assert len(data["blocks"]) == 2


def test_snapshot_to_prompt_serializes_decimal_as_string() -> None:
    data = snapshot_to_prompt_data(_snapshot())
    first = data["blocks"][0]
    assert first["base_fee_gwei"] == "5.0"
    second = data["blocks"][1]
    assert second["base_fee_gwei"] is None
