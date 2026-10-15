"""Tests for LLM JSON extraction. No API calls."""

import pytest

from chainmind.llm.client import LLMError, _extract_json, _to_report


def test_extract_bare_json() -> None:
    text = '{"a": 1}'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_with_markdown_fence() -> None:
    text = 'Here is the report:\n```json\n{"a": 1, "b": 2}\n```'
    assert _extract_json(text) == {"a": 1, "b": 2}


def test_extract_json_with_prose_prefix() -> None:
    text = 'Sure! {"a": 1} that is my answer.'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_raises_on_garbage() -> None:
    with pytest.raises(LLMError):
        _extract_json("no json here")


def test_extract_json_raises_on_unclosed_brace() -> None:
    with pytest.raises(LLMError):
        _extract_json('{"a": 1')


def test_to_report_full_valid() -> None:
    parsed = {
        "headline": "Network is calm",
        "summary": "Recent blocks show low utilization.",
        "observations": [
            {
                "category": "network_congestion",
                "severity": "low",
                "summary": "Gas utilization averages 30%.",
                "evidence": ["gas_used 9M vs gas_limit 30M"],
            }
        ],
        "confidence": 0.7,
        "caveats": ["Cannot infer price from block data"],
    }
    report = _to_report(parsed, "test-model")
    assert report.headline == "Network is calm"
    assert len(report.observations) == 1
    assert report.confidence == pytest.approx(0.7)
    assert report.model == "test-model"


def test_to_report_handles_missing_fields() -> None:
    parsed: dict = {}
    report = _to_report(parsed, "test-model")
    assert report.headline == "(no headline)"
    assert report.confidence == pytest.approx(0.5)
    assert report.observations == []


def test_to_report_clamps_confidence() -> None:
    parsed = {"confidence": 99.0}
    report = _to_report(parsed, "m")
    assert report.confidence == pytest.approx(1.0)

    parsed = {"confidence": -5.0}
    report = _to_report(parsed, "m")
    assert report.confidence == pytest.approx(0.0)


def test_to_report_skips_invalid_observations() -> None:
    parsed = {
        "observations": [
            {"category": "a", "severity": "low", "summary": "ok"},
            "not-a-dict",
            {"category": "b"},  # missing summary -> will use empty string, validation fails
        ],
    }
    report = _to_report(parsed, "m")
    # First observation should be valid, others skipped or defaulted.
    assert len(report.observations) >= 1
