from __future__ import annotations

from mindmesh.context.collector import FileContext
from mindmesh.context.redactor import REDACTED, SecretRedactor


def _redactor() -> SecretRedactor:
    return SecretRedactor()


def _fc(content: str, path: str = "test.py") -> FileContext:
    return FileContext(path=path, content=content, language="python", scope_type="file")


# ---------------------------------------------------------------------------
# Individual pattern tests
# ---------------------------------------------------------------------------


def test_openai_api_key_redacted() -> None:
    content = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890"
    redacted, findings = _redactor().redact(content, "cfg.py")

    assert "sk-" not in redacted
    assert REDACTED in redacted
    assert len(findings) == 1
    assert findings[0].pattern == "openai_api_key"
    assert findings[0].line == 1
    assert findings[0].file == "cfg.py"


def test_aws_access_key_redacted() -> None:
    content = "key = AKIAIOSFODNN7EXAMPLE"
    redacted, findings = _redactor().redact(content, "aws.py")

    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "aws_access_key"


def test_aws_secret_key_redacted() -> None:
    # 40-char base64-ish value
    secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    content = f"AWS_SECRET_ACCESS_KEY={secret}"
    redacted, findings = _redactor().redact(content, "env.py")

    assert secret not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "aws_secret_key"


def test_github_pat_redacted() -> None:
    token = "ghp_" + "A" * 36
    redacted, findings = _redactor().redact(token, "cfg.py")

    assert token not in redacted
    assert findings[0].pattern == "github_pat"


def test_github_oauth_redacted() -> None:
    token = "gho_" + "B" * 36
    redacted, findings = _redactor().redact(token, "cfg.py")

    assert token not in redacted
    assert findings[0].pattern == "github_oauth"


def test_gitlab_pat_redacted() -> None:
    token = "glpat-abcdef1234567890abcd"
    redacted, findings = _redactor().redact(token, "cfg.py")

    assert token not in redacted
    assert findings[0].pattern == "gitlab_pat"


def test_slack_token_redacted() -> None:
    token = "xoxb-" + "1234567890" + "1-abcdefghijklmn"
    redacted, findings = _redactor().redact(token, "slack.py")

    assert token not in redacted
    assert findings[0].pattern == "slack_token"


def test_stripe_key_redacted() -> None:
    key = "sk_live_" + "z" * 24
    redacted, findings = _redactor().redact(key, "pay.py")

    assert key not in redacted
    assert findings[0].pattern == "stripe_key"


def test_google_api_key_redacted() -> None:
    key = "AIza" + "A" * 35
    redacted, findings = _redactor().redact(key, "g.py")

    assert key not in redacted
    assert findings[0].pattern == "google_api_key"


def test_pem_header_redacted() -> None:
    content = "-----BEGIN RSA PRIVATE KEY-----"
    redacted, findings = _redactor().redact(content, "key.pem")

    assert "PRIVATE KEY" not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "pem_private_key"


def test_ssh_rsa_key_redacted() -> None:
    key = "ssh-rsa AAAA" + "B" * 40
    redacted, findings = _redactor().redact(key, "id_rsa.pub")

    assert "AAAA" not in redacted
    assert findings[0].pattern == "ssh_rsa_key"


def test_ssh_ed25519_key_redacted() -> None:
    key = "ssh-ed25519 AAAA" + "C" * 30
    redacted, findings = _redactor().redact(key, "id_ed25519.pub")

    assert "AAAA" not in redacted
    assert findings[0].pattern == "ssh_ed25519_key"


def test_password_assignment_redacted() -> None:
    content = 'password = "secret123"'
    redacted, findings = _redactor().redact(content, "cfg.py")

    assert "secret123" not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "password_assignment"


def test_secret_assignment_redacted() -> None:
    content = "secret: 'mysecretvalue'"
    redacted, findings = _redactor().redact(content, "cfg.yml")

    assert "mysecretvalue" not in redacted
    assert findings[0].pattern == "secret_assignment"


def test_token_assignment_redacted() -> None:
    content = 'token = "tok_abc123"'
    redacted, findings = _redactor().redact(content, "auth.py")

    assert "tok_abc123" not in redacted
    assert findings[0].pattern == "token_assignment"


def test_postgresql_url_redacted() -> None:
    content = "DB=postgresql://user:pass@localhost:5432/mydb"
    redacted, findings = _redactor().redact(content, "db.py")

    assert "user:pass" not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "postgresql_url"


def test_mongodb_url_redacted() -> None:
    content = "uri = mongodb+srv://user:pass@cluster.mongodb.net/db"
    redacted, findings = _redactor().redact(content, "db.py")

    assert "user:pass" not in redacted
    assert findings[0].pattern == "mongodb_url"


def test_redis_url_redacted() -> None:
    content = "REDIS_URL=redis://:password@127.0.0.1:6379"
    redacted, findings = _redactor().redact(content, "cfg.py")

    assert "password" not in redacted.split("=")[1]
    assert findings[0].pattern == "redis_url"


def test_mysql_url_redacted() -> None:
    content = "mysql://root:rootpass@db:3306/app"
    redacted, findings = _redactor().redact(content, "cfg.py")

    assert "rootpass" not in redacted
    assert findings[0].pattern == "mysql_url"


def test_bearer_token_redacted() -> None:
    content = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"
    redacted, findings = _redactor().redact(content, "req.py")

    assert "eyJ" not in redacted
    assert findings[0].pattern == "bearer_token"


# ---------------------------------------------------------------------------
# Behavioural / edge case tests
# ---------------------------------------------------------------------------


def test_normal_code_unchanged() -> None:
    content = "def greet(name: str) -> str:\n    return f'Hello, {name}!'"
    redacted, findings = _redactor().redact(content, "app.py")

    assert redacted == content
    assert findings == []


def test_multiple_secrets_on_one_line_all_redacted() -> None:
    key1 = "sk-" + "a" * 20
    key2 = "sk-" + "b" * 20
    content = f"a={key1} b={key2}"
    redacted, findings = _redactor().redact(content, "cfg.py")

    assert key1 not in redacted
    assert key2 not in redacted
    assert len(findings) == 2


def test_finding_has_correct_line_number() -> None:
    content = "x = 1\nOPENAI=sk-" + "z" * 20 + "\ny = 2"
    _, findings = _redactor().redact(content, "cfg.py")

    assert findings[0].line == 2


def test_finding_correct_file_and_pattern() -> None:
    content = "ghp_" + "X" * 36
    _, findings = _redactor().redact(content, "my/path/file.py")

    assert findings[0].file == "my/path/file.py"
    assert findings[0].pattern == "github_pat"
    assert findings[0].action == "redacted"


def test_redact_files_returns_new_file_contexts() -> None:
    original = _fc('password = "hunter2"')
    r = _redactor()
    new_files, findings = r.redact_files([original])

    assert len(new_files) == 1
    assert new_files[0] is not original
    assert "hunter2" not in new_files[0].content
    assert REDACTED in new_files[0].content
    # original unchanged
    assert original.content == 'password = "hunter2"'
    assert len(findings) == 1


def test_redact_files_preserves_metadata() -> None:
    fc = FileContext(
        path="src/foo.ts",
        content="const k = 'Bearer abc123def456'",
        language="typescript",
        scope_type="diff",
        start_line=1,
        end_line=1,
    )
    new_files, _ = _redactor().redact_files([fc])

    result = new_files[0]
    assert result.path == fc.path
    assert result.language == fc.language
    assert result.scope_type == fc.scope_type
    assert result.start_line == fc.start_line


def test_extra_pattern_redacts() -> None:
    r = SecretRedactor(extra_patterns=[r"MY_SECRET_\w+"])
    content = "x = MY_SECRET_VALUE"
    redacted, findings = r.redact(content, "cfg.py")

    assert "MY_SECRET_VALUE" not in redacted
    assert REDACTED in redacted
    assert findings[0].pattern == "custom_0"


def test_empty_content_no_error() -> None:
    redacted, findings = _redactor().redact("", "empty.py")

    assert redacted == ""
    assert findings == []


def test_multiline_content_correct_line_numbers() -> None:
    lines = [
        "x = 1",
        "y = 2",
        "API=sk-" + "m" * 20,
        "z = 3",
        'DB=postgresql://u:p@host/db',
    ]
    content = "\n".join(lines)
    _, findings = _redactor().redact(content, "cfg.py")

    line_map = {f.pattern: f.line for f in findings}
    assert line_map["openai_api_key"] == 3
    assert line_map["postgresql_url"] == 5


def test_trailing_newline_preserved() -> None:
    content = 'password = "abc"\n'
    redacted, _ = _redactor().redact(content, "f.py")

    assert redacted.endswith("\n")


def test_no_trailing_newline_preserved() -> None:
    content = 'password = "abc"'
    redacted, _ = _redactor().redact(content, "f.py")

    assert not redacted.endswith("\n")


# ---------------------------------------------------------------------------
# Entropy-based detection tests
# ---------------------------------------------------------------------------


def test_entropy_detects_high_entropy_hex() -> None:
    # 32-char string with 32 distinct chars → entropy = log2(32) = 5.0 bits/char > 4.5
    token = "X5mK9pL2nQ7rG4hJ1dF8bN6yE0uC3iAz"
    redacted, findings = _redactor().redact(token, "cfg.py")

    assert token not in redacted
    assert REDACTED in redacted
    assert len(findings) == 1
    assert findings[0].pattern == "entropy"
    assert findings[0].category == "entropy"


def test_entropy_ignores_normal_code() -> None:
    # camelCase identifier: many repeated letters, entropy well below 4.5
    content = "calculateTotalAmountForUserByDate"
    redacted, findings = _redactor().redact(content, "app.py")

    assert findings == []
    assert redacted == content


def test_entropy_ignores_short_strings() -> None:
    # 10 chars < min 20 — never checked regardless of entropy
    token = "zK9mX2pQ7r"
    redacted, findings = _redactor().redact(token, "f.py")

    assert findings == []
    assert redacted == token


# ---------------------------------------------------------------------------
# Custom pattern from config tests
# ---------------------------------------------------------------------------


def test_custom_pattern_from_config() -> None:
    from mindmesh.config import PrivacyConfig

    config = PrivacyConfig(custom_secret_patterns=[r"MY_CUSTOM_TOKEN_\w+"])
    r = SecretRedactor(extra_patterns=config.custom_secret_patterns)
    content = "x = MY_CUSTOM_TOKEN_abc123"
    redacted, findings = r.redact(content, "cfg.py")

    assert "MY_CUSTOM_TOKEN_abc123" not in redacted
    assert REDACTED in redacted
    assert len(findings) == 1
    assert findings[0].category == "custom"


def test_multiple_custom_patterns() -> None:
    from mindmesh.config import PrivacyConfig

    config = PrivacyConfig(custom_secret_patterns=[r"PAT_\w+", r"SEC_\w+"])
    r = SecretRedactor(extra_patterns=config.custom_secret_patterns)
    content = "a=PAT_abc b=SEC_xyz"
    _, findings = r.redact(content, "cfg.py")

    assert len(findings) == 2
    assert all(f.category == "custom" for f in findings)


# ---------------------------------------------------------------------------
# Pattern category tests
# ---------------------------------------------------------------------------


def test_pattern_category_reported() -> None:
    r = _redactor()

    # api_key category
    _, findings_api = r.redact("sk-" + "a" * 25, "f.py")
    assert findings_api[0].category == "api_key"

    # entropy category — 32 distinct chars, entropy = 5.0 bits/char
    _, findings_entropy = r.redact("X5mK9pL2nQ7rG4hJ1dF8bN6yE0uC3iAz", "f.py")
    assert findings_entropy[0].category == "entropy"

    # custom category
    r2 = SecretRedactor(extra_patterns=[r"MY_PAT_\w+"])
    _, findings_custom = r2.redact("x=MY_PAT_abc123", "f.py")
    assert findings_custom[0].category == "custom"
