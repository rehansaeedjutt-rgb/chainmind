"""Tests for chainmind.schemas."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from chainmind.schemas import BlockSummary, ChainSnapshot, ResearchReport


def _block() -> BlockSummary:
    return BlockSummary(
        number=1,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        gas_used=15_000_000,
        gas_limit=30_000_000,
        transaction_count=150,
        base_fee_gwei=Decimal("5.5"),
    )


def test_block_gas_utilization() -> None:
    assert _block().gas_utilization_pct == pytest.approx(50.0)


def test_block_rejects_zero_gas_limit() -> None:
    with pytest.raises(ValidationError):
        BlockSummary(
            number=1,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            gas_used=1,
            gas_limit=0,
            transaction_count=1,
        )


def test_block_immutable() -> None:
    b = _block()
    with pytest.raises(ValidationError):
        b.number = 2  # type: ignore[misc]


def test_snapshot_aggregates() -> None:
    blocks = [_block(), _block(), _block()]
    snap = ChainSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        head_block=100,
        blocks=blocks,
    )
    assert snap.avg_gas_used == 15_000_000
    assert snap.avg_tx_per_block == pytest.approx(150.0)


def test_snapshot_empty_aggregates_return_zero() -> None:
    snap = ChainSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        head_block=100,
        blocks=[],
    )
    assert snap.avg_gas_used == 0
    assert snap.avg_tx_per_block == 0.0


def test_report_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ResearchReport(
            headline="x",
            summary="y",
            confidence=1.5,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            model="m",
        )
