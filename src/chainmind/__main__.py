"""CLI entry point for chainmind."""

from __future__ import annotations

import argparse
import asyncio
import sys

from chainmind import __version__
from chainmind.chain.reader import fetch_snapshot, snapshot_to_prompt_data
from chainmind.config import get_settings
from chainmind.llm.client import GroqClient, LLMError
from chainmind.report.console import print_report, print_snapshot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chainmind",
        description="Real LLM + on-chain data pipeline.",
    )
    parser.add_argument("--version", action="version", version=f"chainmind {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Fetch a chain snapshot (no LLM).")
    snap.add_argument("--blocks", type=int, default=None)

    analyze = sub.add_parser("analyze", help="Fetch a snapshot and analyze with LLM.")
    analyze.add_argument("--blocks", type=int, default=None)

    return parser


async def _run_snapshot(blocks: int | None) -> int:
    settings = get_settings()
    n = blocks if blocks is not None else settings.blocks_to_scan
    print(f"Fetching last {n} blocks from {settings.rpc_url}...\n")
    snapshot = await fetch_snapshot(settings.rpc_url, n)
    print_snapshot(snapshot)
    return 0


async def _run_analyze(blocks: int | None) -> int:
    settings = get_settings()
    n = blocks if blocks is not None else settings.blocks_to_scan

    print(f"Fetching last {n} blocks from {settings.rpc_url}...\n")
    snapshot = await fetch_snapshot(settings.rpc_url, n)
    print_snapshot(snapshot)

    print("Sending to Groq for analysis...\n")
    try:
        client = GroqClient()
    except LLMError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    prompt_data = snapshot_to_prompt_data(snapshot)
    try:
        report = client.analyze_snapshot(prompt_data)
    except LLMError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    print_report(report)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        return asyncio.run(_run_snapshot(args.blocks))
    if args.command == "analyze":
        return asyncio.run(_run_analyze(args.blocks))
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
