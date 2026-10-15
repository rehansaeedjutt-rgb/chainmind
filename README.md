# chainmind

> Real LLM + on-chain data pipeline. AI-powered market research from live chain state.

[![CI](https://github.com/rehansaeedjutt-rgb/chainmind/actions/workflows/ci.yml/badge.svg)](https://github.com/rehansaeedjutt-rgb/chainmind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## What this is

`chainmind` pulls live Ethereum data (recent blocks, gas usage, transaction
counts), sends it to a real LLM (Groq), and produces a structured market
research report. Structured as in: typed Pydantic output, not prose.

This is not a mock. It calls a real API and validates real inference. If
the API key is missing, it fails loudly rather than silently degrading.

## Why this project exists

Most "AI for crypto" demos are either:
- A chatbot wrapper over a price API, or
- A prompt library with no structured output and no way to verify claims.

`chainmind` does something narrower and more honest: it takes a specific,
falsifiable dataset (recent block data), sends it to a real model, and
asks for a structured analysis where every numeric claim must come from
the provided data. The output is validated against a Pydantic schema, so
the model cannot return prose pretending to be JSON.

It is a small pipeline, not a product. The interesting part is the
discipline: structured input, structured output, real API, no fake
intelligence.

## Live demo

Requires a free Groq API key (500k tokens/day, no credit card):

    # 1. Get a key at https://console.groq.com/keys
    # 2. Add it to .env
    cp .env.example .env
    # edit .env, set GROQ_API_KEY=gsk_...

    # 3. Fetch a chain snapshot (no LLM, works without a key)
    chainmind snapshot --blocks 5

    # 4. Full pipeline: fetch + analyze
    chainmind analyze --blocks 5

Example output (chain snapshot stage):

    === Chain snapshot ===
    Head block:        26139603
    Blocks scanned:    5
    Avg tx/block:      182.4
    Avg gas used:      21,547,893

    Per-block detail:
      #26139599    txs=156    util= 28.4%  baseFee=0.198 gwei
      #26139600    txs=204    util= 32.1%  baseFee=0.201 gwei
      #26139601    txs=177    util= 30.7%  baseFee=0.196 gwei
      #26139602    txs=189    util= 35.2%  baseFee=0.212 gwei
      #26139603    txs=186    util= 31.9%  baseFee=0.199 gwei

Example output (LLM stage):

    === LLM report ===
    Model:      llama-3.3-70b-versatile
    Confidence: 0.72

    HEADLINE: Ethereum network operating at moderate utilization

    Recent blocks show steady transaction throughput between 156 and 204
    transactions per block, with gas utilization averaging around 31%.
    Base fees remain low and stable, suggesting there is no urgent
    demand pressure on block space.

    Observations:
      [network_congestion / low] Utilization averages 31.6% across 5 blocks.
          evidence: gas_used between 28.4% and 35.2% of gas_limit
      [fee_environment / low] Base fee is stable within 0.196-0.212 gwei.
          evidence: max/min ratio of 1.08x across the window
      [activity_level / medium] Transaction counts show moderate variance.
          evidence: 156 to 204 transactions per block (30% range)

    Caveats (things the model says it cannot determine):
      - Cannot infer price direction from block data alone
      - Five blocks is a small sample; trends require longer windows
      - No mempool data; only confirmed transactions are visible

    Reminder: this is AI output, not financial advice.

The LLM output varies between runs. The schema does not.

## What is in here

- **Chain reader** — async fetch of recent blocks via public JSON-RPC.
  Handles partial failures: a missing block does not kill the snapshot.
- **Groq LLM client** — real API calls, JSON-mode response, Pydantic
  validation. Strips markdown fences when the model adds them anyway.
- **Structured output** — `ResearchReport` with typed observations,
  confidence score, and preserved caveats.
- **CLI** — two subcommands: `snapshot` (no LLM) and `analyze` (full
  pipeline).
- **19 tests** covering schema invariants, JSON extraction, and prompt
  data shaping. No network calls in tests.
- **GitHub Actions CI** on Python 3.12, 3.13, 3.14.

## What is NOT here (deliberately)

- **No RAG over historical blocks.** Every run fetches fresh data. A
  proper research tool would keep a vector store of prior snapshots.
- **No multi-agent debate.** That is `agentforge`'s job; this project
  is a single-call pipeline. Adding a debate loop here would just be
  `agentforge` again with a different prompt.
- **No price data.** The model is explicitly told not to speculate on
  prices because it does not have them. This is a feature.
- **No cost tracking per run.** Groq free tier is generous; a paid
  deployment would need usage accounting.
- **No caching.** Same input costs the same tokens every run.

## Install

    git clone https://github.com/rehansaeedjutt-rgb/chainmind.git
    cd chainmind
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1   # Windows
    pip install -e ".[dev]"

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `GROQ_API_KEY` | (none) | From console.groq.com/keys |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Model name |
| `CHAINMIND_RPC_URL` | `https://ethereum.publicnode.com` | On-chain endpoint |
| `CHAINMIND_BLOCKS_TO_SCAN` | `5` | Block window size |

## Project structure

    chainmind/
    ├── src/chainmind/
    │   ├── config.py            # Settings
    │   ├── schemas.py           # BlockSummary, ChainSnapshot, ResearchReport
    │   ├── chain/
    │   │   └── reader.py        # Async RPC fetch + prompt shaping
    │   ├── llm/
    │   │   └── client.py        # Groq client + JSON extraction
    │   ├── report/
    │   │   └── console.py       # Terminal formatting
    │   └── __main__.py          # CLI
    ├── tests/unit/              # 19 tests
    ├── pyproject.toml
    └── README.md

## Design notes

**Structured input, structured output.** The prompt demands a specific
JSON schema and the response is parsed with Pydantic. If the model
returns prose, the pipeline fails. That is deliberate — silent fallback
to prose is how "AI tools" end up producing text nobody can use.

**Strip markdown fences when present.** Groq's JSON mode usually returns
clean JSON, but not always. The extractor handles the fenced case and
the "Sure! {...}" case. This is a small ugly function that exists
because real LLMs are not perfectly obedient.

**Do not invent values.** If the model omits `confidence`, we default to
0.5 rather than raising. If it omits `observations`, we return an empty
list. But we never *fabricate* an observation the model did not
produce. The README says this and the code enforces it.

**No price speculation.** The system prompt explicitly forbids price
claims. The model has no price data and any price-related output would
be a hallucination. Blocking this at the prompt level is cheaper than
post-hoc filtering.

**Fail loud on missing API key.** `LLMError` is raised at client
construction. The CLI prints the message and exits with a non-zero code.
The alternative (silent fallback to a mock) would make the project feel
like a demo rather than a tool.

## Testing

    pytest --cov=src/chainmind --cov-report=term-missing

Current coverage: 42% overall. The gap is entirely in:
- `__main__.py` (CLI — exercised manually)
- `chain/reader.py` (needs a live RPC endpoint)
- `llm/client.py` (needs a real API key)
- `report/console.py` (pure formatting)

The schemas, JSON extraction, and prompt-shaping logic are all covered
at 93-96%.

## Roadmap

- [ ] Cache LLM responses by snapshot hash
- [ ] Persist reports to SQLite for historical analysis
- [ ] Multi-block-window trend analysis (hour-over-hour)
- [ ] Add whale transfer detection to the snapshot
- [ ] Second provider (OpenAI-compatible) as a drop-in swap
- [ ] `--json` output flag for CI integration

## Disclaimer

Research and educational tool. AI outputs are not financial advice. The
model has no price data and the README explicitly says so; treat the
candle-free analysis accordingly.

## License

MIT - see [LICENSE](LICENSE).

## Author

**Muhammad Rehan Saeed** - [GitHub](https://github.com/rehansaeedjutt-rgb)