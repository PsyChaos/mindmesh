from __future__ import annotations

import math
import re

from mindmesh.context.collector import FileContext
from mindmesh.schemas import RedactionFinding

REDACTED = "[REDACTED_SECRET]"

# (name, raw_pattern, category) — compiled once at class init
_DEFAULT_PATTERNS: list[tuple[str, str, str]] = [
    # API keys
    ("openai_api_key", r"sk-[a-zA-Z0-9]{20,}", "api_key"),
    ("aws_access_key", r"AKIA[0-9A-Z]{16}", "api_key"),
    ("aws_secret_key", r"AWS_SECRET[_A-Z]*\s*[=:]\s*[A-Za-z0-9/+=]{40}", "api_key"),
    ("github_pat", r"ghp_[a-zA-Z0-9]{36}", "api_key"),
    ("github_oauth", r"gho_[a-zA-Z0-9]{36}", "api_key"),
    ("gitlab_pat", r"glpat-[a-zA-Z0-9\-]{20,}", "api_key"),
    ("slack_token", r"xox[bpors]-[a-zA-Z0-9\-]{10,}", "api_key"),
    ("stripe_key", r"sk_live_[a-zA-Z0-9]{24,}", "api_key"),
    ("google_api_key", r"AIza[0-9A-Za-z\-_]{35}", "api_key"),
    # PEM / SSH
    ("pem_private_key", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "pem"),
    ("ssh_rsa_key", r"ssh-rsa AAAA[a-zA-Z0-9+/=]{20,}", "ssh"),
    ("ssh_ed25519_key", r"ssh-ed25519 AAAA[a-zA-Z0-9+/=]{20,}", "ssh"),
    # key=value / key: value assignments
    ("password_assignment", r"""password\s*[=:]\s*["'][^"']+["']""", "password"),
    ("secret_assignment", r"""secret\s*[=:]\s*["'][^"']+["']""", "password"),
    ("token_assignment", r"""token\s*[=:]\s*["'][^"']+["']""", "password"),
    ("api_key_assignment", r"""api_key\s*[=:]\s*["'][^"']+["']""", "password"),
    # Connection strings
    ("postgresql_url", r"postgresql://[^\s]+", "connection_string"),
    ("mongodb_url", r"mongodb(?:\+srv)?://[^\s]+", "connection_string"),
    ("redis_url", r"redis://[^\s]+", "connection_string"),
    ("mysql_url", r"mysql://[^\s]+", "connection_string"),
    # Bearer token
    ("bearer_token", r"Bearer [a-zA-Z0-9\-._~+/]+=*", "bearer"),
]

_ENTROPY_MIN_LENGTH = 20
_ENTROPY_THRESHOLD = 4.5

# Tokens eligible for entropy check: alnum + base64/url-safe special chars, min 20 chars
_ENTROPY_TOKEN_RE = re.compile(r"[a-zA-Z0-9+/=_\-]{20,}")

_COMMON_WORDS: frozenset[str] = frozenset({
    "import", "function", "class", "return", "define",
    "module", "export", "default", "const", "let", "var",
    "async", "await", "yield", "lambda", "abstract",
    "interface", "implements", "extends", "isinstance",
    "hasattr", "getattr", "setattr", "print", "range",
    "list", "dict", "tuple", "set", "string", "integer",
    "boolean", "object", "array", "true", "false", "none",
    "null", "undefined", "require", "include",
})


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    total = len(s)
    return -sum((count / total) * math.log2(count / total) for count in freq.values())


def _is_high_entropy_secret(token: str) -> bool:
    if len(token) < _ENTROPY_MIN_LENGTH:
        return False
    if token.lower() in _COMMON_WORDS:
        return False
    return _shannon_entropy(token) > _ENTROPY_THRESHOLD


_COMPILED_DEFAULTS: list[tuple[str, str, re.Pattern[str]]] = [
    (name, category, re.compile(raw)) for name, raw, category in _DEFAULT_PATTERNS
]


class SecretRedactor:
    def __init__(self, extra_patterns: list[str] | None = None) -> None:
        compiled = list(_COMPILED_DEFAULTS)
        for i, raw in enumerate(extra_patterns or []):
            compiled.append((f"custom_{i}", "custom", re.compile(raw)))
        self._patterns = compiled

    def redact(self, content: str, file_path: str) -> tuple[str, list[RedactionFinding]]:
        findings: list[RedactionFinding] = []
        redacted_lines: list[str] = []

        for line_num, line in enumerate(content.splitlines(), start=1):
            current = line
            for name, category, pattern in self._patterns:
                matches = list(pattern.finditer(current))
                for _ in matches:
                    findings.append(
                        RedactionFinding(
                            file=file_path, line=line_num, pattern=name, category=category
                        )
                    )
                if matches:
                    current = pattern.sub(REDACTED, current)
            # Entropy check on already-redacted line (only catches what regex missed)
            for match in _ENTROPY_TOKEN_RE.finditer(current):
                token = match.group()
                start = match.start()
                # Skip tokens that appear to be URL path segments (preceded by '/')
                if start > 0 and current[start - 1] == "/":
                    continue
                if _is_high_entropy_secret(token):
                    findings.append(
                        RedactionFinding(
                            file=file_path,
                            line=line_num,
                            pattern="entropy",
                            category="entropy",
                        )
                    )
                    current = current.replace(token, REDACTED, 1)
            redacted_lines.append(current)

        redacted = "\n".join(redacted_lines)
        if content.endswith("\n"):
            redacted += "\n"
        return redacted, findings

    def redact_files(
        self, files: list[FileContext]
    ) -> tuple[list[FileContext], list[RedactionFinding]]:
        all_findings: list[RedactionFinding] = []
        new_files: list[FileContext] = []

        for fc in files:
            redacted_content, findings = self.redact(fc.content, fc.path)
            all_findings.extend(findings)
            new_files.append(fc.model_copy(update={"content": redacted_content}))

        return new_files, all_findings
