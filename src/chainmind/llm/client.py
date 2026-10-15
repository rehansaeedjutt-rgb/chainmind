"""Groq LLM client with structured-output parsing.

Why Groq:
- Free tier: 500,000 tokens/day, no credit card.
- OpenAI-compatible API surface, so the code is easy to port later.
- Fast enough that a multi-block analysis finishes in a couple of
  seconds, which matters for a CLI demo.

The client sends a strict JSON schema in the prompt and validates the
response with Pydantic. This is deliberately more brittle than a
function-calling API because I want to see what the model actually
produces, not what the tool-call wrapper hides.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from groq import Groq

from chainmind.config import get_settings
from chainmind.schemas import MarketObservation, ResearchReport

logger = structlog.get_logger(__name__)


class LLMError(RuntimeError):
    """Raised when the LLM call fails or produces unparseable output."""


# Prompt template. Kept as a module constant so it can be diffed and
# version-controlled — prompt changes are code changes.
_SYSTEM_PROMPT = """You are a crypto market analyst. You will receive a
snapshot of recent Ethereum mainnet block data. Your job is to produce a
structured JSON report analyzing network activity.

You MUST respond with a single JSON object, no prose, no markdown fences.
The JSON must match this schema exactly:

{
  "headline": "one sentence, under 100 chars",
  "summary": "3-5 sentences of analysis grounded in the provided data",
  "observations": [
    {
      "category": "network_congestion | activity_level | fee_environment",
      "severity": "low | medium | high",
      "summary": "one sentence",
      "evidence": ["specific numbers from the data"]
    }
  ],
  "confidence": 0.0 to 1.0,
  "caveats": ["things you cannot determine from this data"]
}

Rules:
- Every numeric claim in evidence must come from the provided data.
- Do not speculate about prices. You have no price data.
- Do not produce more than 5 observations.
- Confidence should reflect how much signal 5 blocks actually contain.
"""


def _build_user_prompt(snapshot_data: dict[str, Any]) -> str:
    """Serialize the chain snapshot into a compact prompt."""
    return (
        "Recent Ethereum block snapshot:\n"
        f"{json.dumps(snapshot_data, indent=2)}\n\n"
        "Analyze the above and produce the JSON report."
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of the model output.

    Groq sometimes wraps JSON in markdown fences even when told not to.
    This function handles that case, and raises if nothing parseable is
    found.
    """
    stripped = text.strip()

    # Strip markdown fence if present.
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)

    # Find first { ... last } as a fallback.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < 0 or end <= start:
        msg = f"No JSON object found in LLM output: {text[:200]}"
        raise LLMError(msg)

    candidate = stripped[start : end + 1]
    try:
        return json.loads(candidate)  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        msg = f"Failed to parse JSON from LLM output: {exc}"
        raise LLMError(msg) from exc


class GroqClient:
    """Thin wrapper over the Groq chat completions endpoint."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        key = api_key if api_key is not None else settings.groq_api_key
        if not key:
            msg = (
                "GROQ_API_KEY is not set.\n"
                "Get a free key at https://console.groq.com/keys and add it to .env"
            )
            raise LLMError(msg)
        self._client = Groq(api_key=key)
        self._model = model or settings.groq_model
        self._max_tokens = settings.max_tokens

    @property
    def model(self) -> str:
        return self._model

    def analyze_snapshot(self, snapshot_data: dict[str, Any]) -> ResearchReport:
        """Send a snapshot to the LLM and parse the structured response."""
        logger.info("llm.request", model=self._model)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(snapshot_data)},
                ],
                temperature=0.2,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # groq raises a variety of errors
            msg = f"Groq API call failed: {exc}"
            raise LLMError(msg) from exc

        content = response.choices[0].message.content
        if content is None:
            msg = "Groq returned empty content"
            raise LLMError(msg)

        parsed = _extract_json(content)
        return _to_report(parsed, self._model)


def _to_report(parsed: dict[str, Any], model: str) -> ResearchReport:
    """Validate the parsed JSON into a ResearchReport.

    The model does not reliably produce the exact schema. We do minor
    coercion here (default missing confidence, drop unknown fields) rather
    than failing — but we do NOT invent values that were not there.
    """
    from datetime import UTC, datetime

    observations: list[MarketObservation] = []
    for raw in parsed.get("observations", []) or []:
        if not isinstance(raw, dict):
            continue
        try:
            observations.append(
                MarketObservation(
                    category=str(raw.get("category", "general")),
                    severity=str(raw.get("severity", "medium")),
                    summary=str(raw.get("summary", "")),
                    evidence=[str(e) for e in (raw.get("evidence") or [])],
                )
            )
        except Exception as exc:
            logger.warning("llm.observation_invalid", error=str(exc))

    confidence_raw = parsed.get("confidence", 0.5)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return ResearchReport(
        headline=str(parsed.get("headline", "(no headline)"))[:200],
        summary=str(parsed.get("summary", "(no summary)")),
        observations=observations,
        confidence=confidence,
        caveats=[str(c) for c in (parsed.get("caveats") or [])],
        generated_at=datetime.now(UTC),
        model=model,
    )
