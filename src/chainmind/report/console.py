"""Console report formatter."""

from __future__ import annotations

from chainmind.schemas import ChainSnapshot, ResearchReport


def print_snapshot(snapshot: ChainSnapshot) -> None:
    """Print the raw chain snapshot before sending it to the LLM."""
    print("=== Chain snapshot ===")
    print(f"Head block:        {snapshot.head_block}")
    print(f"Blocks scanned:    {len(snapshot.blocks)}")
    print(f"Avg tx/block:      {snapshot.avg_tx_per_block:.1f}")
    print(f"Avg gas used:      {snapshot.avg_gas_used:,}")
    print()
    print("Per-block detail:")
    for b in snapshot.blocks:
        base_fee = f"{b.base_fee_gwei} gwei" if b.base_fee_gwei is not None else "n/a"
        print(
            f"  #{b.number:<10}  txs={b.transaction_count:<5}  "
            f"util={b.gas_utilization_pct:5.1f}%  baseFee={base_fee}"
        )
    print()


def print_report(report: ResearchReport) -> None:
    """Print the structured LLM report."""
    print("=== LLM report ===")
    print(f"Model:      {report.model}")
    print(f"Confidence: {report.confidence:.2f}")
    print()
    print(f"HEADLINE: {report.headline}")
    print()
    print(report.summary)
    print()

    if report.observations:
        print("Observations:")
        for obs in report.observations:
            print(f"  [{obs.category} / {obs.severity}] {obs.summary}")
            for e in obs.evidence:
                print(f"      evidence: {e}")
        print()

    if report.caveats:
        print("Caveats (things the model says it cannot determine):")
        for c in report.caveats:
            print(f"  - {c}")
        print()

    print("Reminder: this is AI output, not financial advice.")
