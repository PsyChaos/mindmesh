"""Tests for PromptLoader."""

import pytest

from mindmesh.prompts import PromptLoader
from mindmesh.schemas import Message


@pytest.fixture
def loader() -> PromptLoader:
    return PromptLoader()


def test_review_template_loads(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=["bugs", "security"],
        context="diff content here",
        scope_description=None,
    )
    assert len(messages) == 2


def test_review_returns_message_types(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=["bugs"],
        context="some diff",
        scope_description=None,
    )
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert isinstance(messages[0], Message)
    assert isinstance(messages[1], Message)


def test_focus_areas_rendered_in_system(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=["security", "performance"],
        context="ctx",
        scope_description=None,
    )
    assert "security" in messages[0].content
    assert "performance" in messages[0].content


def test_context_goes_to_user_message(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=[],
        context="my special diff context",
        scope_description=None,
    )
    assert "my special diff context" in messages[1].content


def test_scope_description_in_user_message(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=[],
        context="ctx",
        scope_description="git_diff",
    )
    assert "Scope: git_diff" in messages[1].content


def test_scope_description_none_omits_scope_line(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=[],
        context="ctx",
        scope_description=None,
    )
    assert "Scope:" not in messages[1].content


def test_empty_focus_areas_produces_clean_output(loader: PromptLoader) -> None:
    messages = loader.load(
        "review",
        focus_areas=[],
        context="ctx",
        scope_description=None,
    )
    # System message should still be valid — no leftover loop artifacts
    assert messages[0].content.strip() != ""
    assert "{% for" not in messages[0].content


def test_nonexistent_template_raises_file_not_found(loader: PromptLoader) -> None:
    with pytest.raises(FileNotFoundError):
        loader.load("does_not_exist", context="x")


def test_security_template_loads(loader: PromptLoader) -> None:
    messages = loader.load(
        "security",
        focus_areas=["input_validation", "secrets"],
        context="code snippet here",
        scope_description=None,
    )
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"


def test_security_focus_areas_rendered(loader: PromptLoader) -> None:
    messages = loader.load(
        "security",
        focus_areas=["authentication", "authorization", "injection"],
        context="ctx",
        scope_description=None,
    )
    assert "authentication" in messages[0].content
    assert "authorization" in messages[0].content
    assert "injection" in messages[0].content


def test_security_context_in_user_message(loader: PromptLoader) -> None:
    messages = loader.load(
        "security",
        focus_areas=[],
        context="def vulnerable_query(uid):\n    execute(f'SELECT * FROM users WHERE id={uid}')",
        scope_description="static analysis",
    )
    assert "def vulnerable_query" in messages[1].content
    assert "Scope: static analysis" in messages[1].content


def test_ask_template_loads(loader: PromptLoader) -> None:
    messages = loader.load(
        "ask",
        question="What is the best way to handle errors?",
        context=None,
        context_mode="none",
    )
    assert len(messages) == 2


def test_ask_question_rendered(loader: PromptLoader) -> None:
    messages = loader.load(
        "ask",
        question="How should I implement caching?",
        context=None,
        context_mode="none",
    )
    assert "How should I implement caching?" in messages[1].content


def test_ask_context_optional(loader: PromptLoader) -> None:
    messages = loader.load(
        "ask",
        question="What is wrong with this code?",
        context="def my_func():\n    return None",
        context_mode="file",
    )
    assert "def my_func" in messages[1].content
    assert "Code context:" in messages[1].content


def test_ask_context_mode_none(loader: PromptLoader) -> None:
    messages = loader.load(
        "ask",
        question="What patterns work best here?",
        context=None,
        context_mode="none",
    )
    # When context_mode is "none", the context reference line should not appear
    assert "You have been given code context" not in messages[0].content


def test_bug_investigate_template_loads(loader: PromptLoader) -> None:
    messages = loader.load(
        "bug_investigate",
        issue="Application crashes on startup",
        logs=None,
        context=None,
    )
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"


def test_bug_investigate_issue_rendered(loader: PromptLoader) -> None:
    messages = loader.load(
        "bug_investigate",
        issue="NullPointerException in user authentication",
        logs=None,
        context=None,
    )
    assert "NullPointerException in user authentication" in messages[1].content


def test_bug_investigate_logs_optional(loader: PromptLoader) -> None:
    messages_with_logs = loader.load(
        "bug_investigate",
        issue="Database connection failed",
        logs="ERROR: Connection timeout after 30s",
        context=None,
    )
    assert "Logs:" in messages_with_logs[1].content
    assert "Connection timeout" in messages_with_logs[1].content

    messages_without_logs = loader.load(
        "bug_investigate",
        issue="Database connection failed",
        logs=None,
        context=None,
    )
    assert "Logs:" not in messages_without_logs[1].content


def test_bug_investigate_context_optional(loader: PromptLoader) -> None:
    messages_with_context = loader.load(
        "bug_investigate",
        issue="Race condition detected",
        logs=None,
        context="def race_prone_func():\n    global state\n    state += 1",
    )
    assert "Code context:" in messages_with_context[1].content
    assert "race_prone_func" in messages_with_context[1].content

    messages_without_context = loader.load(
        "bug_investigate",
        issue="Race condition detected",
        logs=None,
        context=None,
    )
    assert "Code context:" not in messages_without_context[1].content
