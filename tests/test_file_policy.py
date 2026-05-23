from __future__ import annotations

import pytest

from mindmesh.config import PrivacyConfig
from mindmesh.policy.file_policy import FilePolicy


@pytest.fixture
def policy() -> FilePolicy:
    return FilePolicy(PrivacyConfig())


@pytest.fixture
def empty_policy() -> FilePolicy:
    return FilePolicy(PrivacyConfig(block_files=[], block_dirs=[]))


class TestBlockFiles:
    def test_env_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked(".env") is True

    def test_env_local_wildcard(self, policy: FilePolicy) -> None:
        assert policy.is_blocked(".env.local") is True

    def test_env_production_wildcard(self, policy: FilePolicy) -> None:
        assert policy.is_blocked(".env.production") is True

    def test_pem_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("certificate.pem") is True

    def test_key_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("private.key") is True

    def test_secrets_recursive_glob(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("secrets/api_key.txt") is True
        assert policy.is_blocked("secrets/nested/token.txt") is True

    def test_config_production_yml_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("config/production.yml") is True

    def test_config_development_yml_passes(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("config/development.yml") is False


class TestBlockDirs:
    def test_node_modules_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("node_modules/package/index.js") is True

    def test_git_dir_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked(".git/config") is True

    def test_nested_vendor_blocked(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("vendor/package/file.py") is True


class TestAllowedPaths:
    def test_normal_python_file_passes(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("src/main.py") is False


class TestEdgeCases:
    def test_empty_config_blocks_nothing(self, empty_policy: FilePolicy) -> None:
        assert empty_policy.is_blocked(".env") is False
        assert empty_policy.is_blocked("secrets/token.txt") is False
        assert empty_policy.is_blocked("node_modules/index.js") is False

    def test_case_sensitive_env(self, policy: FilePolicy) -> None:
        assert policy.is_blocked(".ENV") is False

    def test_case_sensitive_pem(self, policy: FilePolicy) -> None:
        assert policy.is_blocked("certificate.PEM") is False


class TestFilterPaths:
    def test_filter_separates_allowed_and_blocked(self, policy: FilePolicy) -> None:
        paths = ["src/main.py", ".env", "src/utils.py", "certificate.pem"]
        allowed, blocked = policy.filter_paths(paths)
        assert allowed == ["src/main.py", "src/utils.py"]
        assert blocked == [".env", "certificate.pem"]

    def test_filter_all_allowed(self, policy: FilePolicy) -> None:
        paths = ["src/main.py", "src/utils.py"]
        allowed, blocked = policy.filter_paths(paths)
        assert allowed == paths
        assert blocked == []

    def test_filter_all_blocked(self, policy: FilePolicy) -> None:
        paths = [".env", "private.key"]
        allowed, blocked = policy.filter_paths(paths)
        assert allowed == []
        assert blocked == paths
