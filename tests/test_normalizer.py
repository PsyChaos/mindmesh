from __future__ import annotations

import json
from typing import Any

import pytest

from mindmesh.output.normalizer import ResponseNormalizer


@pytest.fixture
def norm() -> ResponseNormalizer:
    return ResponseNormalizer()


def _finding_json(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "title": "Test finding",
        "explanation": "Some explanation",
        "severity": "high",
        "category": "bug",
        "confidence": 0.9,
    }
    base.update(kwargs)
    return base


def test_parse_valid_list(norm: ResponseNormalizer) -> None:
    raw = json.dumps([_finding_json()])
    result = norm.parse(raw, "ep1", "openai", "gpt-4")
    assert result is not None
    assert len(result) == 1
    assert result[0].title == "Test finding"


def test_parse_findings_dict_format(norm: ResponseNormalizer) -> None:
    data = {"findings": [
        _finding_json(), _finding_json(title="Second", explanation="Ex2"),
    ]}
    raw = json.dumps(data)
    result = norm.parse(raw, "ep1", "openai", "gpt-4")
    assert result is not None
    assert len(result) == 2


def test_parse_code_fence_json(norm: ResponseNormalizer) -> None:
    inner = json.dumps([_finding_json()])
    raw = f"```json\n{inner}\n```"
    result = norm.parse(raw, "ep1", "openai", "gpt-4")
    assert result is not None
    assert len(result) == 1


def test_parse_code_fence_no_lang(norm: ResponseNormalizer) -> None:
    inner = json.dumps([_finding_json()])
    raw = f"```\n{inner}\n```"
    result = norm.parse(raw, "ep1", "openai", "gpt-4")
    assert result is not None
    assert len(result) == 1


def test_parse_invalid_json_returns_none(norm: ResponseNormalizer) -> None:
    result = norm.parse("this is not json at all", "ep1", "openai", "gpt-4")
    assert result is None


def test_parse_adds_endpoint_provider_model(norm: ResponseNormalizer) -> None:
    raw = json.dumps([_finding_json()])
    result = norm.parse(raw, "my-endpoint", "gemini", "gemini-2.5-pro")
    assert result is not None
    f = result[0]
    assert f.endpoint == "my-endpoint"
    assert f.provider == "gemini"
    assert f.model == "gemini-2.5-pro"


def test_parse_missing_severity_defaults_info(norm: ResponseNormalizer) -> None:
    item = {"title": "T", "explanation": "E", "category": "bug"}
    raw = json.dumps([item])
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result is not None
    assert result[0].severity == "info"


def test_parse_invalid_severity_defaults_info(norm: ResponseNormalizer) -> None:
    item = _finding_json(severity="garbage")
    raw = json.dumps([item])
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result is not None
    assert result[0].severity == "info"


def test_parse_missing_confidence_defaults_half(norm: ResponseNormalizer) -> None:
    item = {"title": "T", "explanation": "E", "severity": "low", "category": "bug"}
    raw = json.dumps([item])
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result is not None
    assert result[0].confidence == 0.5


def test_parse_empty_findings_list(norm: ResponseNormalizer) -> None:
    raw = json.dumps([])
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result == []


def test_make_parse_error_finding(norm: ResponseNormalizer) -> None:
    f = norm.make_parse_error_finding("ep", "openai", "gpt-4", "bad json error")
    assert f.severity == "info"
    assert f.category == "system"
    assert f.confidence == 1.0
    assert "bad json error" in f.explanation
    assert f.endpoint == "ep"
    assert f.provider == "openai"
    assert f.model == "gpt-4"


def test_strip_code_fence_no_fence(norm: ResponseNormalizer) -> None:
    raw = '{"findings": []}'
    assert norm.strip_code_fence(raw) == raw


def test_strip_code_fence_nested_backticks(norm: ResponseNormalizer) -> None:
    # Content that has backticks inside should still be parsed from outer fence
    inner = json.dumps([_finding_json(title="has `backtick`", explanation="E")])
    raw = f"```json\n{inner}\n```"
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result is not None
    assert result[0].title == "has `backtick`"


def test_parse_plain_text_returns_none(norm: ResponseNormalizer) -> None:
    result = norm.parse("Here are my findings: blah blah blah", "ep", "openai", "gpt-4")
    assert result is None


def test_parse_large_json(norm: ResponseNormalizer) -> None:
    items = [
        _finding_json(title=f"Finding {i}", explanation=f"Explanation {i}")
        for i in range(500)
    ]
    raw = json.dumps(items)
    result = norm.parse(raw, "ep", "openai", "gpt-4")
    assert result is not None
    assert len(result) == 500
