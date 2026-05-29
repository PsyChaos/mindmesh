# Changelog

## 0.2.1 (2026-05-30)

### Security Fixes
- Fail-closed sandbox: Docker unavailable → error instead of silent local fallback
- Command whitelist: shlex-based exact token match, prevents prefix bypass
- SSRF protection: private/internal IP blocking on custom base_url
- Untrusted config warning when sandbox disabled

### New
- `mindmesh plugin-path` — show installed plugin directory
- `mindmesh update` — upgrade to latest version
- Server graceful startup: warns instead of crashing when no API keys configured
- Local security scanners (bandit + semgrep) — zero API cost
- Context compression (AST skeleton + LLM summarizer)
- Smart commit/PR message generation
- Real token tracking from provider responses
- Optional dependencies: `pip install mindmesh-ai[openai]`, `[gemini]`, `[all]`

### Fixed
- Plugin.json: use `mindmesh-mcp` directly instead of `uv run`
- Config: no-provider warning instead of crash for MCP server stability

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
