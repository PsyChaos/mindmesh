# Changelog

## 0.1.0 (2026-05-27)

Initial release.

### Tools (11 MCP tools)
- `review_code` — multi-provider code review
- `security_audit` — security-focused analysis
- `bug_investigate` — root cause analysis
- `ask_provider` — free-form question (raw text)
- `compare_providers` — cross-provider comparison
- `delegate_task` — task delegation with modes (advisory/planning/etc.)
- `list_endpoints` — endpoint listing with health check
- `preview_context` — context/policy preview
- `validate_policy` — config validation
- `test_patch` — patch testing in isolated worktree
- `local_scan` — local security scanners (bandit/semgrep)

### CLI (18 commands)
- All tools accessible via `mindmesh` CLI
- `commit` / `pr` — AI-generated commit messages and PR descriptions
- `history` / `stats` — run history and token usage dashboard
- `providers` / `add-endpoint` / `remove-endpoint` — endpoint management
- Human-readable output by default, `--json` for machine output
- `--output sarif` for GitHub Code Scanning integration
- `--stream` for live token streaming

### Providers
- OpenAI (native streaming)
- Gemini
- Z.ai
- Ollama (native streaming)
- Centralized ProviderRegistry

### Security
- Secret redaction (regex + entropy-based)
- File/directory block policy
- Provider policy (fail-closed)
- Permission policy
- Command whitelist for test execution
- Docker sandbox for worktree tests

### Features
- SQLite response cache with TTL
- SQLite run history with real token tracking
- Context compression (AST skeleton + LLM summarizer)
- Smart finding merger (title similarity + union-find grouping)
- Custom prompt templates with fallback
- SARIF v2.1.0 output
- GitHub Actions CI/CD workflow
- Audit logging (JSONL + SQLite)
