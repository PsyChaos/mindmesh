# MindMesh

MindMesh is an MCP-based AI provider orchestration layer for Claude Code. Claude remains the decision-maker while external providers (OpenAI, Gemini, Z.ai, Ollama) act as reviewers and consultants — analyzing your code without touching the repository.

## Architecture

```
Claude Code  -->  MindMesh Plugin  -->  MCP Server (stdio)  -->  Provider Router  -->  AI Provider
                                        CLI (Typer)         -->  Provider Router  -->  AI Provider
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `review_code` | Multi-provider code review with structured findings |
| `security_audit` | Security-focused analysis of files or git diff |
| `bug_investigate` | Root cause analysis for a reported bug or error |
| `ask_provider` | Free-form question to a provider (raw text, no JSON parse) |
| `compare_providers` | Run the same task across providers, Finding format |
| `delegate_task` | Delegate with mode: advisory, analysis, review, planning, patch_suggestion |
| `list_endpoints` | Show configured endpoints, optional health check (`check=True`) |
| `preview_context` | Preview context/policy without making provider calls |
| `validate_policy` | Validate policy and config rules |
| `test_patch` | Apply a patch in an isolated git worktree and run tests |
| `local_scan` | Run local security scanners (bandit, semgrep) — no LLM calls |

All pipeline tools support `min_severity`, `dry_run`, and `no_cache` parameters.

## CLI

Entry point: `mindmesh`

| Command | Description |
|---------|-------------|
| `review` | Code review |
| `security` | Security audit |
| `bugfix` | Bug investigation |
| `compare` | Compare providers |
| `delegate` | Delegate task |
| `ask` | Free-form question |
| `list` | List endpoints |
| `preview` | Preview context |
| `validate` | Validate policy |
| `test-patch` | Test a patch in worktree |
| `history` | Browse run history |
| `stats` | Usage statistics dashboard |
| `providers` | List available providers |
| `add-endpoint` | Add an endpoint to `.mindmesh.yml` |
| `remove-endpoint` | Remove an endpoint from `.mindmesh.yml` |
| `scan` | Run local security scanners (no LLM cost) |
| `commit` | Generate commit message from diff |
| `pr` | Generate PR title and description |

**Output formats:**
- Default: human-readable tables/panels
- `--json` on any command for raw JSON
- `--output sarif` on `review` and `security` for SARIF v2.1.0 (GitHub Code Scanning compatible)
- `--stream` on `ask` for live token streaming

## Providers

| Provider | SDK | Streaming |
|----------|-----|-----------|
| OpenAI | `openai` (AsyncOpenAI) | Native |
| Gemini | `google-genai` | Fallback |
| Z.ai | `httpx` | Fallback |
| Ollama | `httpx` | Native |

## Installation

```bash
pip install mindmesh-ai[all]          # OpenAI + Gemini
pip install mindmesh-ai[openai]       # OpenAI only
pip install mindmesh-ai[gemini]       # Gemini only
pip install mindmesh-ai               # Core only (Z.ai + Ollama via httpx)
```

Or with uv:

```bash
uv add "mindmesh-ai[all]"
```

## Quick Start

**Requirements:** Python 3.12+, at least one API key

**1. Set API keys:**

```bash
export OPENAI_API_KEY=sk-...
export GEMINI_API_KEY=AI...
# Or create a .env file in your project root
```

**2. Use the CLI:**

```bash
mindmesh list                          # see configured endpoints
mindmesh review --scope git_diff       # review your changes
mindmesh ask "Is this safe?" --stream  # ask a provider
```

**3. Connect to Claude Code** — add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "mindmesh": {
      "command": "mindmesh-mcp"
    }
  }
}
```

Then talk to Claude naturally: *"Review this diff with OpenAI and Gemini"*

## Plugin Setup

MindMesh includes a Claude Code plugin with skills, agents, and hooks. After `pip install`, the plugin files are located at:

```bash
python -c "import sysconfig; print(sysconfig.get_path('data') + '/share/mindmesh/plugin')"
```

To use as a local plugin, add to your project's `.claude/settings.json`:

```json
{
  "enabledPlugins": {"mindmesh@mindmesh-local": true},
  "extraKnownMarketplaces": {
    "mindmesh-local": {
      "source": {"source": "directory", "path": "<plugin-path-from-above>"}
    }
  }
}
```

**CLI** — run directly:

```bash
uv run mindmesh review --scope git_diff
uv run mindmesh security --scope staged
uv run mindmesh ask "Explain this architecture" --endpoint gemini-default
uv run mindmesh ask "What does this do?" --stream
uv run mindmesh providers
uv run mindmesh add-endpoint fast-review --provider openai --model gpt-4o-mini
uv run mindmesh commit
uv run mindmesh pr
uv run mindmesh scan src/ --scanner bandit
uv run mindmesh list --check
uv run mindmesh history
uv run mindmesh stats
```

## Usage Examples

Once MindMesh is connected, talk to Claude naturally:

- *"Review this diff with OpenAI and Gemini"*
- *"Run a security audit on src/auth"*
- *"Login endpoint is throwing 500 — investigate"*
- *"Ask Gemini about this architecture approach"*
- *"Compare how OpenAI and Gemini rate this PR"*
- *"Delegate a planning task to OpenAI in advisory mode"*
- *"Preview what context would be sent before running review"*
- *"Validate my .mindmesh.yml config"*
- *"Test this patch against the test suite"*
- *"Run a local security scan on src/ with bandit"*

## Configuration

Copy `.mindmesh.example.yml` to `.mindmesh.yml` in your project root. Without a config file, MindMesh auto-discovers endpoints from environment variables (`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc.).

See [`.mindmesh.example.yml`](.mindmesh.example.yml) for the full reference.

Key config sections:

| Section | Controls |
|---------|----------|
| `providers` | Provider endpoints, models, timeouts |
| `privacy` | `block_files`, `block_dirs`, `redact_secrets` |
| `policy` | Provider allow/disable lists, permission rules |
| `cache` | `enabled`, `ttl_seconds` (SQLite response cache) |
| `prompts` | `custom_dir` for custom Jinja2 templates (falls back to built-in) |
| `compression` | `enabled`, `endpoint` — AST skeleton + LLM summarizer with fallback |
| `sandbox` | Docker isolation for `test_patch`: `enabled`, `image`, `network`, `memory_limit` |
| `permissions` | `allowed_test_commands` whitelist, patch/codebase access controls |

## Features

- **Response cache** — SQLite-backed with configurable TTL; skip with `no_cache`
- **Run history** — SQLite storage, browsable via `history` and `stats` commands
- **Secret redaction** — Regex patterns + entropy-based detection; secrets are never stored or logged
- **File policy** — `.env`, `*.pem`, `*.key` blocked by default; configurable block lists
- **Provider policy (fail-closed)** — Disabled providers are hard-blocked, no fallback
- **Permission policy** — Controls for full codebase access, external patches, auto-apply
- **Smart merger** — Title similarity + union-find grouping, cross-endpoint only
- **Worktree isolation** — `test_patch` runs in a disposable git worktree with Docker sandbox
- **Docker sandbox** — Test commands run in read-only, no-network containers; falls back to local if Docker unavailable
- **Command whitelist** — `allowed_test_commands` in config blocks arbitrary command execution
- **Provider registry** — Centralized provider management; `providers`, `add-endpoint`, `remove-endpoint` CLI commands
- **Context compression** — AST skeleton extraction (Python) + LLM summarizer with fallback chain
- **Local scanners** — bandit + semgrep integration, zero API cost, Finding-compatible output
- **Streaming** — `ask --stream` for live token output (OpenAI + Ollama native, others fallback)
- **SARIF output** — v2.1.0, compatible with GitHub Code Scanning
- **GitHub Actions** — Ready-made workflow at `.github/workflows/mindmesh-review.yml`
- **Token tracking** — Real token counts from provider responses in `stats` and `history --detail`
- **Audit logging** — JSONL + SQLite dual logging
- **Custom prompts** — Override built-in Jinja2 templates per project

## Security

- **Redaction**: Secrets are masked before any content leaves your machine. Detected patterns (API keys, PEM blocks, connection strings, high-entropy tokens) are reported as findings — values are never stored or logged.
- **File Policy**: `.env`, `*.pem`, `*.key`, and other sensitive paths are blocked by default. Configurable via `privacy.block_files` / `privacy.block_dirs`.
- **Provider Policy (fail-closed)**: Disabled providers are hard-blocked. No request is sent and no fallback occurs. Partial failures do not cascade — a failing endpoint does not block others.
- **Audit Trail**: All tool invocations are logged to JSONL and SQLite for traceability.

## Entry Points

| Command | Purpose |
|---------|---------|
| `mindmesh-mcp` | MCP server over stdio (for Claude Code) |
| `mindmesh` | CLI for terminal usage |

## Development

```bash
uv run pytest          # run tests
uv run ruff check .    # lint
uv run pyright         # type check
```

## License

MIT
