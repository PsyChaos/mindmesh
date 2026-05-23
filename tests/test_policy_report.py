"""Tests for PolicyReport model and its integration in the review pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mindmesh.config import (
    EndpointConfig,
    LimitsConfig,
    MindMeshConfig,
    PermissionsConfig,
    PrivacyConfig,
    ProviderConfig,
    ReviewConfig,
)
from mindmesh.context.collector import FileContext
from mindmesh.output.merger import MergeResult
from mindmesh.output.report import Reporter
from mindmesh.schemas import PolicyReport, ToolResult
from mindmesh.tools.review import _run_review  # pyright: ignore[reportPrivateUsage]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_JSON = (
    '[{"severity":"high","category":"bug","title":"X",'
    '"explanation":"e","confidence":0.9}]'
)

_FAKE_FILE = FileContext(
    path="src/main.py",
    content="def foo(): pass\n",
    language="python",
    scope_type="diff",
)


def _make_policy_report(**kwargs: object) -> PolicyReport:
    defaults: dict[str, object] = dict(
        checked_providers=["openai"],
        blocked_providers=[],
        allowed_providers=["openai"],
        permission_warnings=[],
        file_policy_blocked=[],
        redacted_secret_count=0,
    )
    defaults.update(kwargs)
    return PolicyReport(**defaults)  # type: ignore[arg-type]


def _make_merge_result(endpoints: list[str] | None = None) -> MergeResult:
    endpoints = endpoints or []
    return MergeResult(
        all_findings=[],
        match_hints=[],
        endpoints_represented=endpoints,
        findings_per_endpoint={},
    )


def _make_config(
    disabled: list[str] | None = None,
    providers: list[str] | None = None,
    permissions: PermissionsConfig | None = None,
) -> MindMeshConfig:
    prov_list = providers or ["openai"]
    return MindMeshConfig(
        providers={p: ProviderConfig() for p in prov_list},
        disabled=disabled or [],
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30)
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(block_files=[], block_dirs=[]),
        limits=LimitsConfig(),
        permissions=permissions or PermissionsConfig(),
    )


def _make_adapter(send_return: str = _VALID_JSON) -> MagicMock:
    adapter = MagicMock()
    adapter.name = "openai"
    adapter.send = AsyncMock(return_value=send_return)
    return adapter


# ---------------------------------------------------------------------------
# PolicyReport model
# ---------------------------------------------------------------------------

def test_policy_report_constructs_correctly() -> None:
    report = PolicyReport(
        checked_providers=["openai", "gemini"],
        blocked_providers=[{
            "provider": "gemini",
            "reason": "disabled",
            "error_code": "PROVIDER_DISABLED",
        }],
        allowed_providers=["openai"],
        permission_warnings=[{"warning": "EXTERNAL_PROVIDER", "details": "openai"}],
        file_policy_blocked=["secrets/.env"],
        redacted_secret_count=3,
    )

    assert report.checked_providers == ["openai", "gemini"]
    assert len(report.blocked_providers) == 1
    assert report.blocked_providers[0]["provider"] == "gemini"
    assert report.blocked_providers[0]["error_code"] == "PROVIDER_DISABLED"
    assert report.allowed_providers == ["openai"]
    assert len(report.permission_warnings) == 1
    assert report.file_policy_blocked == ["secrets/.env"]
    assert report.redacted_secret_count == 3


def test_policy_report_empty_defaults() -> None:
    report = PolicyReport(
        checked_providers=[],
        blocked_providers=[],
        allowed_providers=[],
        permission_warnings=[],
        file_policy_blocked=[],
        redacted_secret_count=0,
    )
    assert report.blocked_providers == []
    assert report.allowed_providers == []


def test_policy_report_model_dump_is_dict() -> None:
    report = _make_policy_report()
    dumped = report.model_dump()
    assert isinstance(dumped, dict)
    assert "checked_providers" in dumped
    assert "blocked_providers" in dumped
    assert "allowed_providers" in dumped
    assert "permission_warnings" in dumped
    assert "file_policy_blocked" in dumped
    assert "redacted_secret_count" in dumped


# ---------------------------------------------------------------------------
# Blocked provider fields
# ---------------------------------------------------------------------------

def test_blocked_provider_has_required_fields() -> None:
    report = _make_policy_report(
        checked_providers=["openai"],
        blocked_providers=[{
            "provider": "openai",
            "reason": "Provider 'openai' is disabled.",
            "error_code": "PROVIDER_DISABLED",
        }],
        allowed_providers=[],
    )
    block = report.blocked_providers[0]
    assert "provider" in block
    assert "reason" in block
    assert "error_code" in block


def test_all_allowed_means_empty_blocked() -> None:
    report = _make_policy_report(
        checked_providers=["openai", "gemini"],
        blocked_providers=[],
        allowed_providers=["openai", "gemini"],
    )
    assert report.blocked_providers == []
    assert len(report.allowed_providers) == 2


# ---------------------------------------------------------------------------
# Permission warnings
# ---------------------------------------------------------------------------

def test_permission_warnings_in_report() -> None:
    report = _make_policy_report(
        permission_warnings=[
            {"warning": "EXTERNAL_PROVIDER", "details": "openai"},
            {"warning": "LARGE_CONTEXT", "details": "size_kb=512, limit_kb=256"},
        ]
    )
    assert len(report.permission_warnings) == 2
    warnings = {w["warning"] for w in report.permission_warnings}
    assert "EXTERNAL_PROVIDER" in warnings
    assert "LARGE_CONTEXT" in warnings


def test_no_warnings_when_none_triggered() -> None:
    report = _make_policy_report(permission_warnings=[])
    assert report.permission_warnings == []


# ---------------------------------------------------------------------------
# ToolResult.policy_report field
# ---------------------------------------------------------------------------

def test_tool_result_policy_report_field_populated() -> None:
    pr = _make_policy_report()
    result = ToolResult(
        summary="done",
        policy_report=pr.model_dump(),
    )
    assert result.policy_report is not None
    assert result.policy_report["checked_providers"] == ["openai"]


def test_tool_result_policy_report_defaults_to_none() -> None:
    result = ToolResult(summary="done")
    assert result.policy_report is None


def test_tool_result_model_dump_includes_policy_report() -> None:
    pr = _make_policy_report(redacted_secret_count=2)
    result = ToolResult(summary="done", policy_report=pr.model_dump())
    d = result.model_dump()
    assert d["policy_report"] is not None
    assert d["policy_report"]["redacted_secret_count"] == 2


# ---------------------------------------------------------------------------
# Reporter.build() with policy_report
# ---------------------------------------------------------------------------

@pytest.fixture
def reporter() -> Reporter:
    return Reporter()


def test_reporter_sets_policy_report_when_provided(reporter: Reporter) -> None:
    pr = _make_policy_report(
        checked_providers=["openai"],
        allowed_providers=["openai"],
        blocked_providers=[],
    )
    result = reporter.build(_make_merge_result(), [], [], 0.0, pr)
    assert result.policy_report is not None
    assert result.policy_report["allowed_providers"] == ["openai"]
    assert result.policy_report["blocked_providers"] == []


def test_reporter_policy_report_none_when_not_provided(reporter: Reporter) -> None:
    result = reporter.build(_make_merge_result(), [], [], 0.0)
    assert result.policy_report is None


def test_reporter_blocked_provider_in_policy_report(reporter: Reporter) -> None:
    pr = _make_policy_report(
        checked_providers=["openai"],
        blocked_providers=[{
            "provider": "openai",
            "reason": "Provider 'openai' is disabled. No fallback.",
            "error_code": "PROVIDER_DISABLED",
        }],
        allowed_providers=[],
    )
    result = reporter.build(_make_merge_result(), [], [], 0.0, pr)
    assert result.policy_report is not None
    assert len(result.policy_report["blocked_providers"]) == 1
    assert result.policy_report["blocked_providers"][0]["error_code"] == "PROVIDER_DISABLED"


def test_reporter_file_policy_blocked_in_policy_report(reporter: Reporter) -> None:
    pr = _make_policy_report(file_policy_blocked=["secrets/token.pem", ".env"])
    result = reporter.build(_make_merge_result(), [], [], 0.0, pr)
    assert result.policy_report is not None
    assert "secrets/token.pem" in result.policy_report["file_policy_blocked"]


def test_reporter_redacted_secret_count_in_policy_report(reporter: Reporter) -> None:
    pr = _make_policy_report(redacted_secret_count=5)
    result = reporter.build(_make_merge_result(), [], [], 0.0, pr)
    assert result.policy_report is not None
    assert result.policy_report["redacted_secret_count"] == 5


# ---------------------------------------------------------------------------
# Integration: _run_review populates policy_report
# ---------------------------------------------------------------------------

async def test_review_pipeline_populates_policy_report() -> None:
    config = _make_config()
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", None, None)

    assert "policy_report" in result
    assert result["policy_report"] is not None
    pr = result["policy_report"]
    assert "openai" in pr["checked_providers"]
    assert "openai" in pr["allowed_providers"]
    assert pr["blocked_providers"] == []


async def test_disabled_provider_appears_in_blocked_providers() -> None:
    config = _make_config(disabled=["openai"])
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", None, None)

    pr = result["policy_report"]
    assert pr is not None
    assert "openai" in pr["checked_providers"]
    assert pr["allowed_providers"] == []
    assert len(pr["blocked_providers"]) == 1
    assert pr["blocked_providers"][0]["provider"] == "openai"
    assert pr["blocked_providers"][0]["error_code"] == "PROVIDER_DISABLED"


async def test_permission_warning_for_external_provider() -> None:
    permissions = PermissionsConfig(require_confirmation_for_external_provider=True)
    config = _make_config(permissions=permissions)
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[_FAKE_FILE])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", None, None)

    pr = result["policy_report"]
    assert pr is not None
    assert any(w["warning"] == "EXTERNAL_PROVIDER" for w in pr["permission_warnings"])


async def test_file_policy_blocked_in_pipeline_policy_report() -> None:
    # Use default PrivacyConfig so .env is in the default block_files list
    config = MindMeshConfig(
        providers={"openai": ProviderConfig()},
        disabled=[],
        endpoints={
            "ep1": EndpointConfig(provider="openai", model="gpt-4o", timeout_seconds=30)
        },
        review=ReviewConfig(default_endpoints=["ep1"]),
        privacy=PrivacyConfig(),  # default block_files includes ".env"
        limits=LimitsConfig(),
    )
    blocked_file = FileContext(
        path=".env",
        content="SECRET=abc\n",
        language="text",
        scope_type="file",
    )
    adapter = _make_adapter()

    with (
        patch("mindmesh.tools.review.GitContext"),
        patch("mindmesh.tools.review.ContextCollector") as mock_cc_cls,
        patch("mindmesh.tools.review.EndpointResolver") as mock_resolver_cls,
    ):
        mock_cc = MagicMock()
        mock_cc.collect = AsyncMock(return_value=[blocked_file])
        mock_cc_cls.return_value = mock_cc
        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = (adapter, "gpt-4o", {"timeout_seconds": 30})
        mock_resolver_cls.return_value = mock_resolver

        result = await _run_review(config, "git_diff", None, None)

    pr = result["policy_report"]
    assert pr is not None
    assert ".env" in pr["file_policy_blocked"]
