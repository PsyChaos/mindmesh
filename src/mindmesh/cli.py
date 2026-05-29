"""MindMesh CLI — Typer interface for MCP tools."""
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from mindmesh.config import load_config

app = typer.Typer(name="mindmesh", help="Multi-provider AI code review and analysis.")


def _run(coro: object) -> object:
    return asyncio.run(coro)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Output helpers — human-readable by default, --json for machine output
# ---------------------------------------------------------------------------

def _json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _print_findings(result: object, as_json: bool, fmt: str = "json") -> None:
    if as_json:
        if fmt == "sarif" and isinstance(result, dict):
            raw = list(result.get("findings", []))  # pyright: ignore[reportUnknownArgumentType]
            if raw:
                from mindmesh.output.sarif import findings_to_sarif
                from mindmesh.schemas import Finding
                _json(findings_to_sarif([Finding.model_validate(f) for f in raw]))
                return
        _json(result)
        return

    if not isinstance(result, dict):
        typer.echo(str(result))
        return

    summary = result.get("summary", "")
    if summary:
        typer.echo(f"\n  {summary}\n")

    findings = result.get("findings", [])
    if findings:
        for f in findings:
            sev = f.get("severity", "?").upper()
            cat = f.get("category", "")
            title = f.get("title", "")
            file = f.get("file", "")
            line = f.get("line")
            loc = f"{file}:{line}" if line else file
            typer.echo(f"  [{sev}] {cat}: {title}")
            if loc:
                typer.echo(f"         {loc}")
            explanation = f.get("explanation", "")
            if explanation:
                typer.echo(f"         {explanation}")
            rec = f.get("recommendation", "")
            if rec:
                typer.echo(f"         → {rec}")
            typer.echo()

    errors = result.get("endpoint_errors", [])
    for err in errors:
        ep = err.get("endpoint", "?")
        code = err.get("error_code", "?")
        msg = err.get("message", "")
        typer.echo(f"  [ERROR] {ep}: {code} — {msg}")

    meta = result.get("metadata", {})
    if meta:
        parts = []
        if "endpoints_called" in meta:
            parts.append(f"endpoints: {meta['endpoints_called']}")
        if "total_findings" in meta:
            parts.append(f"findings: {meta['total_findings']}")
        if "context_size_kb" in meta:
            parts.append(f"context: {meta['context_size_kb']:.1f} KB")
        if parts:
            typer.echo(f"  {' | '.join(parts)}")


def _print_dict(result: object, as_json: bool) -> None:
    if as_json:
        _json(result)
        return
    if not isinstance(result, dict):
        typer.echo(str(result))
        return
    for k, v in result.items():
        if isinstance(v, list):
            typer.echo(f"\n  {k}:")
            for item in v:
                if isinstance(item, dict):
                    parts = [f"{ik}={iv}" for ik, iv in item.items()]
                    typer.echo(f"    {', '.join(parts)}")
                else:
                    typer.echo(f"    {item}")
        elif isinstance(v, dict):
            typer.echo(f"\n  {k}:")
            for ik, iv in v.items():
                typer.echo(f"    {ik}: {iv}")
        else:
            typer.echo(f"  {k}: {v}")


# ---------------------------------------------------------------------------
# Tool commands
# ---------------------------------------------------------------------------

@app.command()
def review(
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    focus: Annotated[str | None, typer.Option(help="Comma-separated focus areas")] = None,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview context only")] = False,
    no_cache: Annotated[bool, typer.Option(help="Skip cache")] = False,
    output: Annotated[str, typer.Option(help="json or sarif")] = "json",
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Run code review via configured endpoints."""
    from mindmesh.tools.review import review_code
    cfg = load_config()
    from mindmesh.tools import review as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    fc = focus.split(",") if focus else None
    result = _run(review_code(
        scope=scope, endpoints=ep, focus=fc,
        dry_run=dry_run, min_severity=min_severity, no_cache=no_cache,
    ))
    _print_findings(result, as_json, output)


@app.command()
def security(
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    focus: Annotated[str | None, typer.Option(help="Comma-separated focus areas")] = None,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview context only")] = False,
    no_cache: Annotated[bool, typer.Option(help="Skip cache")] = False,
    output: Annotated[str, typer.Option(help="json or sarif")] = "json",
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Run security audit via configured endpoints."""
    from mindmesh.tools.security import security_audit
    cfg = load_config()
    from mindmesh.tools import security as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    fc = focus.split(",") if focus else None
    result = _run(security_audit(
        scope=scope, endpoints=ep, focus=fc,
        dry_run=dry_run, min_severity=min_severity, no_cache=no_cache,
    ))
    _print_findings(result, as_json, output)


@app.command()
def bugfix(
    issue: Annotated[str, typer.Argument(help="Bug description")],
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    logs: Annotated[str | None, typer.Option(help="Log content or path")] = None,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview context only")] = False,
    no_cache: Annotated[bool, typer.Option(help="Skip cache")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Investigate a bug via configured endpoints."""
    from mindmesh.tools.bugfix import bug_investigate
    cfg = load_config()
    from mindmesh.tools import bugfix as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    result = _run(bug_investigate(
        issue=issue, scope=scope, endpoints=ep, logs=logs,
        dry_run=dry_run, min_severity=min_severity, no_cache=no_cache,
    ))
    _print_findings(result, as_json)


@app.command()
def compare(
    task: Annotated[str, typer.Argument(help="Task to compare")],
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview context only")] = False,
    no_cache: Annotated[bool, typer.Option(help="Skip cache")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Compare multiple providers on the same task."""
    from mindmesh.tools.compare import compare_providers
    cfg = load_config()
    from mindmesh.tools import compare as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    result = _run(compare_providers(
        task=task, scope=scope, endpoints=ep,
        min_severity=min_severity, dry_run=dry_run, no_cache=no_cache,
    ))
    _print_findings(result, as_json)


@app.command()
def delegate(
    task: Annotated[str, typer.Argument(help="Task to delegate")],
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoint: Annotated[str | None, typer.Option(help="Single endpoint")] = None,
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    mode: Annotated[str, typer.Option(help="Delegation mode")] = "advisory",
    allow_patch: Annotated[bool, typer.Option(help="Allow patches")] = False,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    dry_run: Annotated[bool, typer.Option(help="Preview context only")] = False,
    no_cache: Annotated[bool, typer.Option(help="Skip cache")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Delegate a task to one or more endpoints."""
    from mindmesh.tools.delegate import delegate_task
    cfg = load_config()
    from mindmesh.tools import delegate as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    result = _run(delegate_task(
        task=task, scope=scope, endpoint=endpoint, endpoints=ep,
        mode=mode, allow_patch=allow_patch, min_severity=min_severity,
        dry_run=dry_run, no_cache=no_cache,
    ))
    _print_findings(result, as_json)


@app.command()
def ask(
    question: Annotated[str, typer.Argument(help="Question to ask")],
    endpoint: Annotated[str | None, typer.Option(help="Target endpoint")] = None,
    context_mode: Annotated[str, typer.Option(help="Context mode")] = "none",
    stream: Annotated[bool, typer.Option(help="Stream response live")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Ask a free-form question to a provider."""
    if stream and not as_json:
        _run(_ask_stream(question, endpoint, context_mode))
        return

    from mindmesh.tools.ask import ask_provider
    cfg = load_config()
    from mindmesh.tools import ask as mod
    mod.init_tools(cfg)
    result = _run(ask_provider(
        question=question, endpoint=endpoint, context_mode=context_mode,
    ))

    if as_json:
        _json(result)
    elif isinstance(result, dict):
        answer = result.get("answer")
        error = result.get("error")
        if error:
            typer.echo(f"Error: {error}", err=True)
        elif answer:
            ep = result.get("endpoint", "")
            provider = result.get("provider", "")
            model = result.get("model", "")
            typer.echo(f"[{provider}/{model} via {ep}]\n")
            typer.echo(answer)
    else:
        typer.echo(str(result))


async def _ask_stream(
    question: str, endpoint: str | None, context_mode: str,
) -> None:
    from mindmesh.config import resolve_alias
    from mindmesh.context.collector import ContextCollector, format_context
    from mindmesh.context.filters import ContextFilter
    from mindmesh.context.git import GitContext
    from mindmesh.context.redactor import SecretRedactor
    from mindmesh.errors import MindMeshError
    from mindmesh.policy.file_policy import FilePolicy
    from mindmesh.prompts import PromptLoader
    from mindmesh.providers.base import EndpointResolver

    cfg = load_config()
    defaults = cfg.review.default_endpoints
    ep_name = endpoint or (defaults[0] if defaults else None)
    if not ep_name or ep_name not in cfg.endpoints:
        typer.echo(f"Error: endpoint '{ep_name}' not found", err=True)
        raise typer.Exit(1)

    resolver = EndpointResolver(cfg)
    try:
        adapter, model, ep_dict = resolver.resolve(ep_name)
    except (MindMeshError, KeyError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    context_text = ""
    if context_mode != "none":
        git = GitContext()
        collector = ContextCollector(git, cfg)
        ctx_filter = ContextFilter(FilePolicy(cfg.privacy), cfg.limits)
        redactor = SecretRedactor()
        try:
            raw = await collector.collect(context_mode)
        except Exception:
            raw = []
        filtered, _ = ctx_filter.filter(raw)
        redacted, _ = redactor.redact_files(filtered)
        context_text = format_context(redacted)

    custom_dir = Path(cfg.prompts.custom_dir) if cfg.prompts.custom_dir else None
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load(
        "ask", question=question, context_mode=context_mode,
        context=context_text,
    )

    provider = resolve_alias(cfg.endpoints[ep_name].provider)
    typer.echo(f"[{provider}/{model}] ", nl=False)
    async for chunk in adapter.send_stream(messages, model, ep_dict):
        typer.echo(chunk, nl=False)
    typer.echo()


@app.command(name="list")
def list_eps(
    check: Annotated[bool, typer.Option(help="Run health check")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """List configured endpoints."""
    from mindmesh.tools.list_endpoints import list_endpoints
    cfg = load_config()
    from mindmesh.tools import list_endpoints as mod
    mod.init_tools(cfg)
    result = _run(list_endpoints(check=check))

    if as_json:
        _json(result)
    elif isinstance(result, dict):
        for ep in result.get("endpoints", []):
            name = ep.get("name", "?")
            provider = ep.get("provider", "?")
            model = ep.get("model", "?")
            status = ep.get("status", "?")
            health = ep.get("health", "")
            line = f"  {name:20s} {provider:10s} {model:20s} {status}"
            if health:
                line += f"  ({health})"
            typer.echo(line)
    else:
        typer.echo(str(result))


@app.command()
def preview(
    scope: Annotated[str, typer.Option(help="Context scope")] = "git_diff",
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Preview context and policy without provider calls."""
    from mindmesh.tools.preview import preview_context
    cfg = load_config()
    from mindmesh.tools import preview as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    result = _run(preview_context(scope=scope, endpoints=ep))
    _print_dict(result, as_json)


@app.command()
def validate(
    endpoints: Annotated[str | None, typer.Option(help="Comma-separated endpoints")] = None,
    paths: Annotated[str | None, typer.Option(help="Comma-separated paths")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Validate policy and config."""
    from mindmesh.tools.validate import validate_policy
    cfg = load_config()
    from mindmesh.tools import validate as mod
    mod.init_tools(cfg)
    ep = endpoints.split(",") if endpoints else None
    pa = paths.split(",") if paths else None
    result = _run(validate_policy(endpoints=ep, paths=pa))
    _print_dict(result, as_json)


@app.command(name="test-patch")
def test_patch_cmd(
    patch_file: Annotated[str, typer.Argument(help="Path to patch file")],
    test_command: Annotated[str | None, typer.Option(help="Test command")] = None,
    timeout: Annotated[float, typer.Option(help="Timeout seconds")] = 120.0,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Apply a patch in isolated worktree and optionally run tests."""
    from mindmesh.tools.test_patch import test_patch
    cfg = load_config()
    from mindmesh.tools import test_patch as mod
    mod.init_tools(cfg)
    p = Path(patch_file)
    if not p.exists():
        typer.echo(f"Error: patch file not found: {patch_file}", err=True)
        raise typer.Exit(1)
    result = _run(test_patch(
        patch=p.read_text(), test_command=test_command, timeout=timeout,
    ))
    _print_dict(result, as_json)


@app.command()
def scan(
    target: Annotated[str, typer.Argument(help="Path to scan")] = ".",
    scanner: Annotated[str | None, typer.Option(help="Scanner: bandit, semgrep")] = None,
    min_severity: Annotated[str | None, typer.Option(help="Minimum severity")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Run local security scanners (no LLM calls)."""
    from mindmesh.tools.scan import local_scan
    cfg = load_config()
    from mindmesh.tools import scan as mod
    mod.init_tools(cfg)
    result = _run(local_scan(
        target=target, scanner=scanner, min_severity=min_severity,
    ))
    _print_findings(result, as_json)


# ---------------------------------------------------------------------------
# Git helper commands
# ---------------------------------------------------------------------------


@app.command()
def commit(
    endpoint: Annotated[str | None, typer.Option(help="Endpoint")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Generate a commit message from staged/unstaged changes."""
    _run(_generate_commit(endpoint, as_json))


async def _generate_commit(
    endpoint: str | None, as_json: bool,
) -> None:
    from mindmesh.context.git import GitContext
    from mindmesh.prompts import PromptLoader
    from mindmesh.providers.base import EndpointResolver

    cfg = load_config()
    git = GitContext()
    diff = await git.smart_diff(cfg.project.base_branch)
    if not diff:
        typer.echo("No changes to commit.", err=True)
        raise typer.Exit(1)

    ep_name = endpoint or (
        cfg.review.default_endpoints[0] if cfg.review.default_endpoints else None
    )
    if not ep_name:
        typer.echo("No endpoint configured.", err=True)
        raise typer.Exit(1)

    resolver = EndpointResolver(cfg)
    adapter, model, ep_dict = resolver.resolve(ep_name)

    custom_dir = Path(cfg.prompts.custom_dir) if cfg.prompts.custom_dir else None
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load("commit", diff=diff)

    raw = await adapter.send(messages, model, ep_dict)
    message = raw.strip()

    if as_json:
        _json({"commit_message": message, "endpoint": ep_name})
    else:
        typer.echo(message)


@app.command()
def pr(
    endpoint: Annotated[str | None, typer.Option(help="Endpoint")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Generate a PR title and description from branch changes."""
    _run(_generate_pr(endpoint, as_json))


async def _generate_pr(
    endpoint: str | None, as_json: bool,
) -> None:
    from mindmesh.context.git import GitContext
    from mindmesh.prompts import PromptLoader
    from mindmesh.providers.base import EndpointResolver

    cfg = load_config()
    git = GitContext()
    branch = await git.current_branch()
    commits = await git.branch_log(cfg.project.base_branch)
    diff = await git.smart_diff(cfg.project.base_branch)

    if not diff and not commits:
        typer.echo("No changes for PR.", err=True)
        raise typer.Exit(1)

    ep_name = endpoint or (
        cfg.review.default_endpoints[0] if cfg.review.default_endpoints else None
    )
    if not ep_name:
        typer.echo("No endpoint configured.", err=True)
        raise typer.Exit(1)

    resolver = EndpointResolver(cfg)
    adapter, model, ep_dict = resolver.resolve(ep_name)

    custom_dir = Path(cfg.prompts.custom_dir) if cfg.prompts.custom_dir else None
    loader = PromptLoader(custom_dir=custom_dir)
    messages = loader.load(
        "pr", branch=branch, commits=commits or "(no commits)", diff=diff or "(no diff)",
    )

    raw = await adapter.send(messages, model, ep_dict)

    if as_json:
        _json({
            "branch": branch,
            "raw": raw.strip(),
            "endpoint": ep_name,
        })
    else:
        typer.echo(f"Branch: {branch}\n")
        typer.echo(raw.strip())


# ---------------------------------------------------------------------------
# History & stats commands
# ---------------------------------------------------------------------------

@app.command()
def history(
    count: Annotated[int, typer.Option(help="Number of runs")] = 20,
    detail: Annotated[int | None, typer.Option(help="Show detail for run ID")] = None,
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Show recent run history."""
    from mindmesh.history import HistoryStore
    store = HistoryStore()

    if detail is not None:
        record = store.get(detail)
        store.close()
        if not record:
            typer.echo(f"Run #{detail} not found.", err=True)
            raise typer.Exit(1)
        if as_json:
            _json(asdict(record))
        else:
            typer.echo(f"\n  Run #{record.id}")
            typer.echo(f"  Tool:      {record.tool}")
            typer.echo(f"  Scope:     {record.scope}")
            typer.echo(f"  Status:    {record.status}")
            typer.echo(f"  Time:      {record.timestamp}")
            typer.echo(f"  Duration:  {record.duration_ms}ms")
            typer.echo(f"  Findings:  {record.findings_count}")
            typer.echo(f"  Context:   {record.context_size_kb:.1f} KB")
            typer.echo(f"  Secrets:   {record.redacted_secrets}")
            typer.echo(f"  Tokens:    {record.input_tokens} in / {record.output_tokens} out")
            typer.echo(f"  Endpoints: {', '.join(record.endpoints_called)}")
            if record.endpoints_failed:
                typer.echo(f"  Failed:    {', '.join(record.endpoints_failed)}")
        return

    records = store.recent(count)
    store.close()
    if as_json:
        _json([asdict(r) for r in records])
    elif not records:
        typer.echo("  No runs recorded yet.")
    else:
        typer.echo(
            f"\n  {'ID':>4s}  {'Tool':12s} {'Status':8s} "
            f"{'Findings':>8s} {'Duration':>8s}  Timestamp"
        )
        typer.echo(f"  {'─' * 70}")
        for r in records:
            typer.echo(
                f"  {r.id:4d}  {r.tool:12s} {r.status:8s} "
                f"{r.findings_count:8d} {r.duration_ms:7d}ms"
                f"  {r.timestamp[:19]}"
            )


@app.command()
def stats(
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """Show provider/endpoint statistics."""
    from mindmesh.history import HistoryStore
    store = HistoryStore()
    provider_stats = store.stats()
    store.close()

    if as_json:
        _json([asdict(s) for s in provider_stats])
    elif not provider_stats:
        typer.echo("  No stats yet. Run some commands first.")
    else:
        typer.echo(
            f"\n  {'Endpoint':20s} {'Calls':>6s} {'OK':>4s} "
            f"{'Fail':>4s} {'Rate':>6s} {'Avg ms':>7s} "
            f"{'Findings':>8s} {'Tokens':>10s}"
        )
        typer.echo(f"  {'─' * 70}")
        for s in provider_stats:
            rate = f"{s.success_rate:.0%}"
            tokens = f"{s.total_input_tokens + s.total_output_tokens}"
            typer.echo(
                f"  {s.provider:20s} {s.total_calls:6d} "
                f"{s.successes:4d} {s.failures:4d} "
                f"{rate:>6s} {s.avg_duration_ms:7.0f} "
                f"{s.total_findings:8d} {tokens:>10s}"
            )


@app.command()
def providers(
    as_json: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    """List registered providers."""
    from mindmesh.registry import get_registry
    reg = get_registry()
    infos = reg.all_providers()
    if as_json:
        _json([{
            "name": p.name,
            "module": p.module_path,
            "class": p.class_name,
            "default_model": p.default_model,
            "api_key_env": p.api_key_env,
            "aliases": list(p.aliases),
        } for p in infos])
    else:
        typer.echo(
            f"\n  {'Name':12s} {'Default Model':20s} "
            f"{'API Key Env':20s} Aliases"
        )
        typer.echo(f"  {'─' * 65}")
        for p in infos:
            aliases = ", ".join(p.aliases) if p.aliases else "—"
            env = p.api_key_env or "—"
            typer.echo(
                f"  {p.name:12s} {p.default_model:20s} "
                f"{env:20s} {aliases}"
            )


@app.command(name="add-endpoint")
def add_endpoint(
    name: Annotated[str, typer.Argument(help="Endpoint name (e.g. my-review)")],
    provider: Annotated[str, typer.Option(help="Provider: openai, gemini, zai, ollama")],
    model: Annotated[str, typer.Option(help="Model name (e.g. gpt-5.1)")],
    timeout: Annotated[int, typer.Option(help="Timeout seconds")] = 30,
) -> None:
    """Add an endpoint to .mindmesh.yml."""
    from mindmesh.registry import get_registry
    reg = get_registry()
    resolved = reg.resolve_alias(provider)
    if not reg.is_known(resolved):
        known = ", ".join(sorted(reg.known_names()))
        typer.echo(f"Unknown provider '{provider}'. Known: {known}", err=True)
        raise typer.Exit(1)

    config_path = Path.cwd() / ".mindmesh.yml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        import yaml
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}

    endpoints = raw.setdefault("endpoints", {})
    if name in endpoints:
        typer.echo(f"Endpoint '{name}' already exists.", err=True)
        raise typer.Exit(1)

    endpoints[name] = {
        "provider": resolved,
        "model": model,
        "timeout_seconds": timeout,
    }

    import yaml
    with open(config_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)

    typer.echo(f"Added endpoint '{name}' ({resolved}/{model}) to .mindmesh.yml")


@app.command(name="remove-endpoint")
def remove_endpoint(
    name: Annotated[str, typer.Argument(help="Endpoint name to remove")],
) -> None:
    """Remove an endpoint from .mindmesh.yml."""
    config_path = Path.cwd() / ".mindmesh.yml"
    if not config_path.exists():
        typer.echo("No .mindmesh.yml found.", err=True)
        raise typer.Exit(1)

    import yaml
    with open(config_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    endpoints = raw.get("endpoints", {})
    if name not in endpoints:
        typer.echo(f"Endpoint '{name}' not found.", err=True)
        raise typer.Exit(1)

    del endpoints[name]
    with open(config_path, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)

    typer.echo(f"Removed endpoint '{name}' from .mindmesh.yml")


# ---------------------------------------------------------------------------
# Setup commands
# ---------------------------------------------------------------------------


@app.command(name="plugin-path")
def plugin_path() -> None:
    """Show the installed plugin directory path."""
    import sysconfig

    candidates = [
        Path.home() / ".local/share/uv/tools/mindmesh-ai/share/mindmesh/plugin",
        Path(sysconfig.get_path("data")) / "share/mindmesh/plugin",
    ]
    for p in candidates:
        if p.exists():
            typer.echo(str(p))
            return
    typer.echo("Plugin not found. Reinstall with: uv tool install \"mindmesh-ai[all]\"", err=True)
    raise typer.Exit(1)


@app.command()
def update() -> None:
    """Update mindmesh-ai to the latest version."""
    import subprocess
    typer.echo("Updating mindmesh-ai...")
    result = subprocess.run(
        ["uv", "tool", "upgrade", "mindmesh-ai"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        typer.echo(result.stdout.strip() or "Updated successfully.")
    else:
        fallback = subprocess.run(
            ["pip", "install", "--upgrade", "mindmesh-ai"],
            capture_output=True, text=True,
        )
        if fallback.returncode == 0:
            typer.echo(fallback.stdout.strip() or "Updated successfully.")
        else:
            typer.echo("Update failed. Try manually:", err=True)
            typer.echo('  uv tool upgrade mindmesh-ai')
            typer.echo('  pip install --upgrade mindmesh-ai')
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
