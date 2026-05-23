"""Tests for ResponseCache — SQLite-backed response cache."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mindmesh.cache import ResponseCache
from mindmesh.config import CacheConfig


@pytest.fixture
def cache_db(tmp_path: Path) -> Path:
    return tmp_path / "test_cache.db"


@pytest.fixture
def enabled_cache(cache_db: Path) -> ResponseCache:
    config = CacheConfig(enabled=True, ttl_seconds=60, db_path=str(cache_db))
    return ResponseCache(config)


@pytest.fixture
def disabled_cache() -> ResponseCache:
    return ResponseCache(CacheConfig(enabled=False))


# --- disabled cache ---


def test_disabled_cache_get_returns_none(disabled_cache: ResponseCache) -> None:
    disabled_cache.put("key", "value")
    assert disabled_cache.get("key") is None


def test_disabled_cache_clear_returns_zero(disabled_cache: ResponseCache) -> None:
    assert disabled_cache.clear() == 0


# --- basic get/put ---


def test_put_and_get(enabled_cache: ResponseCache) -> None:
    enabled_cache.put("k1", {"answer": "hello"})
    result = enabled_cache.get("k1")
    assert result == {"answer": "hello"}


def test_get_missing_key(enabled_cache: ResponseCache) -> None:
    assert enabled_cache.get("nonexistent") is None


def test_put_overwrites(enabled_cache: ResponseCache) -> None:
    enabled_cache.put("k1", "first")
    enabled_cache.put("k1", "second")
    assert enabled_cache.get("k1") == "second"


# --- TTL expiry ---


def test_expired_entry_returns_none(cache_db: Path) -> None:
    config = CacheConfig(enabled=True, ttl_seconds=1, db_path=str(cache_db))
    cache = ResponseCache(config)
    cache.put("k1", "value")

    with patch("mindmesh.cache.time") as mock_time:
        mock_time.time.return_value = time.time() + 2
        assert cache.get("k1") is None


def test_non_expired_entry_returns_value(enabled_cache: ResponseCache) -> None:
    enabled_cache.put("k1", "value")
    assert enabled_cache.get("k1") == "value"


# --- clear ---


def test_clear_removes_entries(enabled_cache: ResponseCache) -> None:
    enabled_cache.put("k1", "a")
    enabled_cache.put("k2", "b")
    count = enabled_cache.clear()
    assert count == 2
    assert enabled_cache.get("k1") is None
    assert enabled_cache.get("k2") is None


# --- make_key ---


def test_make_key_deterministic() -> None:
    k1 = ResponseCache.make_key("ep1", "review", "abc123")
    k2 = ResponseCache.make_key("ep1", "review", "abc123")
    assert k1 == k2


def test_make_key_differs_by_endpoint() -> None:
    k1 = ResponseCache.make_key("ep1", "review", "abc123")
    k2 = ResponseCache.make_key("ep2", "review", "abc123")
    assert k1 != k2


def test_make_key_differs_by_template() -> None:
    k1 = ResponseCache.make_key("ep1", "review", "abc123")
    k2 = ResponseCache.make_key("ep1", "security", "abc123")
    assert k1 != k2


def test_make_key_differs_by_context() -> None:
    k1 = ResponseCache.make_key("ep1", "review", "abc")
    k2 = ResponseCache.make_key("ep1", "review", "xyz")
    assert k1 != k2


# --- hash_content ---


def test_hash_content_deterministic() -> None:
    h1 = ResponseCache.hash_content("hello world")
    h2 = ResponseCache.hash_content("hello world")
    assert h1 == h2


def test_hash_content_differs() -> None:
    h1 = ResponseCache.hash_content("hello")
    h2 = ResponseCache.hash_content("world")
    assert h1 != h2


# --- close ---


def test_close_then_get_returns_none(enabled_cache: ResponseCache) -> None:
    enabled_cache.put("k1", "value")
    enabled_cache.close()
    assert enabled_cache.get("k1") is None


# --- db_path auto-creation ---


def test_db_path_parent_created(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "nested" / "cache.db"
    config = CacheConfig(enabled=True, db_path=str(nested))
    cache = ResponseCache(config)
    cache.put("k", "v")
    assert cache.get("k") == "v"
    cache.close()
