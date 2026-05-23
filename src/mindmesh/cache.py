"""Response cache backed by SQLite."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from mindmesh.config import CacheConfig

_DEFAULT_DB = Path.home() / ".mindmesh" / "cache.db"

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS response_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class ResponseCache:
    def __init__(self, config: CacheConfig) -> None:
        self._enabled = config.enabled
        self._ttl = config.ttl_seconds
        if not self._enabled:
            self._conn: sqlite3.Connection | None = None
            return
        db_path = Path(config.db_path) if config.db_path else _DEFAULT_DB
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(_INIT_SQL)
        self._conn.commit()

    @staticmethod
    def make_key(
        endpoint: str,
        template: str,
        context_hash: str,
        extra: str = "",
    ) -> str:
        raw = f"{endpoint}:{template}:{context_hash}:{extra}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    def hash_content(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def get(self, key: str) -> str | None:
        if not self._enabled or self._conn is None:
            return None
        row = self._conn.execute(
            "SELECT value, created_at FROM response_cache WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        value, created_at = row
        if time.time() - created_at > self._ttl:
            self._conn.execute(
                "DELETE FROM response_cache WHERE key = ?", (key,),
            )
            self._conn.commit()
            return None
        return json.loads(value)

    def put(self, key: str, value: object) -> None:
        if not self._enabled or self._conn is None:
            return
        self._conn.execute(
            "INSERT OR REPLACE INTO response_cache (key, value, created_at) "
            "VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()

    def clear(self) -> int:
        if not self._enabled or self._conn is None:
            return 0
        cursor = self._conn.execute("DELETE FROM response_cache")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
