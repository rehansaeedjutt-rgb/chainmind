"""Pydantic models for the pipeline."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BlockSummary(BaseModel):
    """A single block's key metrics. Extracted from raw RPC."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(..., ge=0)
    timestamp: datetime
    gas_used: int = Field(..., ge=0)
    gas_limit: int = Field(..., gt=0)
    transaction_count: int = Field(..., ge=0)
    base_fee_gwei: Decimal | None = None

    @property
    def gas_utilization_pct(self) -> float:
        if self.gas_limit == 0:
            return 0.0
        return (self.gas_used / self.gas_limit) * 100.0


class ChainSnapshot(BaseModel):
    """A multi-block snapshot for LLM analysis."""

    model_config = ConfigDict(frozen=True)

    captured_at: datetime
    head_block: int = Field(..., ge=0)
    blocks: list[BlockSummary]

    @property
    def avg_gas_used(self) -> int:
        if not self.blocks:
            return 0
        return sum(b.gas_used for b in self.blocks) // len(self.blocks)

    @property
    def avg_tx_per_block(self) -> float:
        if not self.blocks:
            return 0.0
        return sum(b.transaction_count for b in self.blocks) / len(self.blocks)


class MarketObservation(BaseModel):
    """Single observation from the LLM, structured."""

    model_config = ConfigDict(frozen=True)

    category: str = Field(..., min_length=1, description="e.g. network_congestion, activity_level")
    severity: str = Field(..., description="low | medium | high")
    summary: str = Field(..., min_length=1)
    evidence: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Final structured report from the LLM."""

    model_config = ConfigDict(frozen=True)

    headline: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    observations: list[MarketObservation] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    caveats: list[str] = Field(default_factory=list)
    generated_at: datetime
    model: str
