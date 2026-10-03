"""Claude Code CLI backend (provider ``claude-cli``, benchmark infrastructure).

Lets a run use the operator's existing Claude login (for example a Claude Max
subscription) instead of a separately billed API key. Each model call runs the
Claude Code CLI once, non-interactively::

    claude -p --output-format json --model MODEL --system-prompt-file FILE \\
        --tools "" --safe-mode --strict-mcp-config --disable-slash-commands \\
        --no-session-persistence [--effort LEVEL]      < rendered conversation

What is sent:
- the request's ``system`` text, byte for byte, as the system prompt (via a file,
  so size limits on command-line arguments do not apply);
- the conversation on stdin: a single user message verbatim, or, for a
  multi-turn request, every turn in order under ``=== user ===`` /
  ``=== assistant ===`` headers after a fixed one-line preamble. The CLI takes
  one prompt per call, so turns are serialized rather than sent as separate
  API messages.

Isolation of the call:
- ``--tools ""`` gives the model no tools at all, so it cannot read files,
  run commands or browse;
- ``--safe-mode`` turns off CLAUDE.md files, hooks, skills, plugins, MCP
  servers and other customizations while keeping normal login;
- ``--strict-mcp-config`` (with no config) loads no MCP servers;
- ``--no-session-persistence`` keeps no transcript;
- the process runs in an empty private directory, outside the repository;
- no ``--fallback-model``: a fallback would change the model mid-run and
  break the equality of contestants;
- ``ANTHROPIC_API_KEY``/``ANTHROPIC_AUTH_TOKEN`` are removed from the CLI's
  environment (unless ``TAB_CLAUDE_CLI_KEEP_API_KEY=1``), so the call is billed
  to the subscription login, not to an API key that happens to be set.

What is reported, and only what the CLI reports (nothing is estimated here):
- tokens from the result's ``usage`` (uncached input, cache reads, cache
  writes, output); if they are missing the call is marked
  ``usage_available: false`` and every token field is ``null``;
- the served model from ``modelUsage`` (the entry whose counts match
  ``usage``); other entries are the CLI's own auxiliary calls and are
  reported apart (``auxiliary_*``);
- ``total_cost_usd`` as ``cost_usd`` with ``cost_basis: provider_reported``.
  It is the CLI's list-price equivalent of the call (including its auxiliary
  calls), **not** what a subscription is charged;
- thinking tokens, turn count and CLI version in ``provider_meta``; the CLI's
  own timings under ``provider_meta.latency_ms`` (volatile).

Limitations compared with the API (also in docs/milestone-2-design.md):
- the CLI adds its own context to every request (a short preamble, an
  environment block with the working directory, platform, model identity and
  today's real date, and account reminders); measured at roughly 1.2k input
  tokens. It is the same for every contestant and contains nothing from the
  benchmark, but the prompt is not exactly the harness's;
- no temperature control (rejected at configuration time), no per-call
  output-token cap (``CLAUDE_CODE_MAX_OUTPUT_TOKENS`` is set only when the run
  configures ``max_output_tokens``, and the CLI then *fails* an over-long reply
  instead of truncating it), no stop sequences (emulated by cutting the
  returned text; output tokens are still those generated);
- subscription usage limits and rate limits apply; when the login or the
  usage limit fails the backend raises :class:`ProviderUnavailable`, and the
  runner stops the run instead of continuing with incomparable steps;
- one CLI process per call: slower than the API (seconds of start-up each).
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Mapping

from harness.agent import ModelSettings
from harness.errors import ToolError
from harness.llm import ModelRequest
from harness.model.gateway import PROVIDER_ERROR_PREFIX, ProviderUnavailable, RawCompletion

__all__ = [
    "ClaudeCliBackend",
    "build_command",
    "build_env",
    "render_prompt",
    "parse_cli_output",
    "TRANSCRIPT_PREAMBLE",
    "DEFAULT_TIMEOUT_S",
]

ENV_BINARY = "TAB_CLAUDE_BIN"
ENV_TIMEOUT = "TAB_CLAUDE_CLI_TIMEOUT_S"
ENV_KEEP_API_KEY = "TAB_CLAUDE_CLI_KEEP_API_KEY"
CREDENTIAL_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
DEFAULT_TIMEOUT_S = 900.0
TRANSCRIPT_PREAMBLE = (
    "The conversation so far is reproduced below, turn by turn and in order. "
    "Write only the next assistant turn."
)
_ERR = f"{PROVIDER_ERROR_PREFIX}: claude-cli"


# -------------------------------------------------------------- pure helpers
def render_prompt(request: ModelRequest) -> str:
    """The text sent on stdin: one user message verbatim, or the whole transcript with role headers."""
    msgs = request.messages
    if len(msgs) == 1:
        return msgs[0].content
    parts = [TRANSCRIPT_PREAMBLE]
    for m in msgs:
        parts.append(f"=== {m.role} ===\n{m.content}")
    return "\n\n".join(parts)


def build_command(binary: str, settings: ModelSettings, system_prompt_file: Path) -> list[str]:
    if not settings.name:
        raise ValueError("model provider 'claude-cli' requires a model name")
    cmd = [
        binary,
        "-p",
        "--output-format", "json",
        "--model", settings.name,
        "--system-prompt-file", str(system_prompt_file),
        "--tools", "",
        "--safe-mode",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
    ]
    if settings.effort:
        cmd += ["--effort", settings.effort]
    return cmd


def build_env(environ: Mapping[str, str], settings: ModelSettings) -> dict[str, str]:
    """The CLI inherits the operator's environment (it needs the login), minus API-key variables."""
    env = dict(environ)
    if env.get(ENV_KEEP_API_KEY) != "1":
        for key in CREDENTIAL_ENV:
            env.pop(key, None)
    for key in (ENV_BINARY, ENV_TIMEOUT, ENV_KEEP_API_KEY):
        env.pop(key, None)
    env.pop("CLAUDE_CODE_MAX_OUTPUT_TOKENS", None)
    if settings.max_output_tokens:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(settings.max_output_tokens)
    return env


def _count(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else None


def _model_counts(entry: Mapping[str, Any]) -> tuple[int, int, int, int] | None:
    vals = tuple(_count(entry.get(k)) for k in ("inputTokens", "outputTokens", "cacheReadInputTokens",
                                                  "cacheCreationInputTokens"))
    return None if any(v is None for v in vals) else vals  # type: ignore[return-value]


def _classify_error(data: Mapping[str, Any]) -> ToolError:
    text = str(data.get("result") or "")
    low = text.lower()
    status = data.get("api_error_status")
    subtype = str(data.get("subtype") or "error")
    if "usage limit" in low or "limit reached" in low or ("rate_limit" in low and "usage" in low):
        return ProviderUnavailable(f"{_ERR}: usage limit reached for this Claude login")
    if status in (401, 403) or any(s in low for s in ("/login", "not logged in", "invalid api key", "authentication",
                                                        "oauth token", "unauthorized")):
        return ProviderUnavailable(f"{_ERR}: not authenticated (run `claude` once in a terminal and log in)")
    if "output token maximum" in low:
        return ToolError(f"{_ERR}: reply exceeded CLAUDE_CODE_MAX_OUTPUT_TOKENS")
    if "overloaded" in low or status in (429, 500, 502, 503, 529):
        return ToolError(f"{_ERR}: provider temporarily unavailable (status {status})")
    return ToolError(f"{_ERR}: error result ({subtype}, status {status})")


def _find_result(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()
    candidates = [text] + [line for line in reversed(text.splitlines()) if line.lstrip().startswith("{")]
    for c in candidates:
        try:
            obj = json.loads(c)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("type") == "result":
            return obj
    return None


def parse_cli_output(
    stdout: str, settings: ModelSettings, request: ModelRequest, *, cli_version: str | None = None
) -> RawCompletion:
    """Turn ``claude -p --output-format json`` output into a :class:`RawCompletion` (or raise ToolError)."""
    data = _find_result(stdout)
    if data is None:
        raise ToolError(f"{_ERR}: output was not a JSON result object")
    if data.get("is_error") or data.get("subtype") != "success":
        raise _classify_error(data)
    text = data.get("result")
    if not isinstance(text, str):
        raise ToolError(f"{_ERR}: result has no text")

    usage = data.get("usage") if isinstance(data.get("usage"), Mapping) else {}
    top = tuple(_count(usage.get(k)) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                "cache_creation_input_tokens"))
    usage_available = all(v is not None for v in top)

    models: dict[str, dict[str, Any]] = {}
    raw_models = data.get("modelUsage") if isinstance(data.get("modelUsage"), Mapping) else {}
    primary_key: str | None = None
    for key in sorted(raw_models):
        entry = raw_models[key]
        if not isinstance(entry, Mapping):
            continue
        counts = _model_counts(entry)
        cost = entry.get("costUSD")
        models[key] = {
            "canonical_model": entry.get("canonicalModel") if isinstance(entry.get("canonicalModel"), str) else None,
            "input_tokens": counts[0] if counts else None,
            "output_tokens": counts[1] if counts else None,
            "cache_read_input_tokens": counts[2] if counts else None,
            "cache_creation_input_tokens": counts[3] if counts else None,
            "cost_usd": round(float(cost), 8) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
            "cost_basis": entry.get("costBasis") if isinstance(entry.get("costBasis"), str) else None,
        }
        if usage_available and counts is not None and (counts[0], counts[1], counts[2], counts[3]) == top:
            primary_key = primary_key or key
    if primary_key is None:
        for key, m in models.items():
            if settings.name in (key, m["canonical_model"]):
                primary_key = key
                break
    if primary_key is None and len(models) == 1:
        primary_key = next(iter(models))
    if primary_key is not None:
        served = models[primary_key]["canonical_model"] or primary_key
    else:
        served = settings.name or "unknown"

    aux_in = aux_out = 0
    for key, m in models.items():
        if key == primary_key:
            continue
        aux_in += sum(m[k] or 0 for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        aux_out += m["output_tokens"] or 0

    cost = data.get("total_cost_usd")
    reported_cost = round(float(cost), 8) if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost >= 0 else None

    stop_reason = data.get("stop_reason") if isinstance(data.get("stop_reason"), str) else "end_turn"
    stops_cut = False
    for stop in request.stop:
        i = text.find(stop)
        if i >= 0:
            text, stop_reason, stops_cut = text[:i], "stop_sequence", True
    details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), Mapping) else {}
    meta: dict[str, Any] = {
        "cli_version": cli_version,
        "served_model_key": primary_key,
        "models": models,
        "num_turns": _count(data.get("num_turns")),
        "thinking_tokens": _count(details.get("thinking_tokens")),
        "service_tier": usage.get("service_tier") if isinstance(usage.get("service_tier"), str) else None,
        "cost_note": "total_cost_usd as reported by the Claude CLI (list-price equivalent; not subscription billing)",
        "stop_sequences_emulated": stops_cut,
        "max_output_tokens_enforced": bool(settings.max_output_tokens),
        "latency_ms": {
            "duration": data.get("duration_ms"),
            "api": data.get("duration_api_ms"),
            "ttft": data.get("ttft_ms"),
        },
    }
    return RawCompletion(
        text=text,
        stop_reason=stop_reason,
        model=served,
        input_tokens=top[0] if usage_available else 0,  # type: ignore[arg-type]
        output_tokens=top[1] if usage_available else 0,  # type: ignore[arg-type]
        cache_read_input_tokens=top[2] if usage_available else 0,  # type: ignore[arg-type]
        cache_creation_input_tokens=top[3] if usage_available else 0,  # type: ignore[arg-type]
        usage_available=usage_available,
        reported_cost_usd=reported_cost,
        auxiliary_input_tokens=aux_in,
        auxiliary_output_tokens=aux_out,
        meta=meta,
    )


# --------------------------------------------------------------------- backend
class ClaudeCliBackend:
    """Completion backend that runs the Claude Code CLI once per call."""

    name = "claude-cli"

    def __init__(self, *, environ: Mapping[str, str] = os.environ, binary: str | None = None) -> None:
        self._environ = dict(environ)
        self.binary = binary or self._environ.get(ENV_BINARY) or "claude"
        try:
            self.timeout_cap = float(self._environ.get(ENV_TIMEOUT) or DEFAULT_TIMEOUT_S)
        except ValueError:
            raise ValueError(f"{ENV_TIMEOUT} must be a number of seconds") from None
        self._scratch: Path | None = None
        self._version: str | None = None
        self._version_checked = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------- utilities
    def _scratch_dir(self) -> Path:
        if self._scratch is None:
            self._scratch = Path(tempfile.mkdtemp(prefix="tab-claude-cli-"))
            (self._scratch / "cwd").mkdir()
            (self._scratch / "prompts").mkdir()
        return self._scratch

    def cli_version(self) -> str | None:
        if not self._version_checked:
            self._version_checked = True
            try:
                out = subprocess.run([self.binary, "--version"], capture_output=True, text=True, timeout=30,
                                     env=build_env(self._environ, ModelSettings()), stdin=subprocess.DEVNULL)
                self._version = out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None
            except (OSError, subprocess.SubprocessError):
                self._version = None
        return self._version

    def runtime_info(self) -> dict[str, Any]:
        keep = self._environ.get(ENV_KEEP_API_KEY) == "1"
        return {
            "backend": self.name,
            "claude_cli_version": self.cli_version(),
            "api_key_env_removed": not keep,
            "timeout_cap_s": self.timeout_cap,
        }

    def close(self) -> None:
        if self._scratch is not None:
            shutil.rmtree(self._scratch, ignore_errors=True)
            self._scratch = None

    # ------------------------------------------------------------- the call
    def complete(
        self,
        request: ModelRequest,
        settings: ModelSettings,
        *,
        max_output_tokens: int,
        timeout_s: float | None,
        lane: str,
    ) -> RawCompletion:
        with self._lock:  # one CLI process at a time: calls are sequential in the lockstep runner anyway
            scratch = self._scratch_dir()
            prompt_file = Path(tempfile.mkstemp(prefix="system-", suffix=".txt", dir=scratch / "prompts")[1])
            try:
                prompt_file.write_text(request.system, encoding="utf-8")
                cmd = build_command(self.binary, settings, prompt_file)
                limit = self.timeout_cap if timeout_s is None else min(self.timeout_cap, float(timeout_s))
                stdout, stderr, code = self._run(cmd, render_prompt(request), build_env(self._environ, settings),
                                                 scratch / "cwd", limit)
            finally:
                prompt_file.unlink(missing_ok=True)
        if _find_result(stdout) is None:
            self._raise_for_process_failure(code, stderr)
        return parse_cli_output(stdout, settings, request, cli_version=self.cli_version())

    def _run(self, cmd: list[str], prompt: str, env: dict[str, str], cwd: Path, limit: float) -> tuple[str, str, int]:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=cwd, env=env, start_new_session=True)
        except FileNotFoundError:
            raise ProviderUnavailable(
                f"{_ERR}: the claude executable was not found (install Claude Code or set {ENV_BINARY})"
            ) from None
        except OSError as exc:
            raise ProviderUnavailable(f"{_ERR}: could not start the claude executable ({type(exc).__name__})") from None
        try:
            out, err = proc.communicate(input=prompt.encode("utf-8"), timeout=limit)
        except subprocess.TimeoutExpired:
            self._kill(proc)
            proc.communicate()
            raise ToolError(f"{_ERR}: timed out after {round(limit)} s") from None
        finally:
            self._kill(proc)
        return out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), proc.returncode

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def _raise_for_process_failure(self, code: int, stderr: str) -> None:
        low = stderr.lower()
        if "unknown option" in low or "unknown argument" in low or "error: option" in low:
            raise ProviderUnavailable(
                f"{_ERR}: this Claude Code version lacks an option the benchmark needs; update it (claude update)"
            )
        if "/login" in low or "not logged in" in low or "authentication" in low or "invalid api key" in low:
            raise ProviderUnavailable(f"{_ERR}: not authenticated (run `claude` once in a terminal and log in)")
        if "usage limit" in low or "limit reached" in low:
            raise ProviderUnavailable(f"{_ERR}: usage limit reached for this Claude login")
        if "another claude code session" in low:
            raise ProviderUnavailable(f"{_ERR}: refused to start inside another Claude Code session")
        raise ToolError(f"{_ERR}: exited with code {code} without a result")

    # ------------------------------------------------------------- preflight
    def check(self, settings: ModelSettings, timeout_s: float = 180.0) -> dict[str, Any]:
        """One tiny call to confirm the CLI, the login and the model work before a long run."""
        from harness.llm import ModelMessage

        req = ModelRequest(system="You are a connectivity check for a benchmark harness.",
                           messages=(ModelMessage("user", "Reply with the single word: ready"),), purpose="preflight")
        raw = self.complete(req, settings, max_output_tokens=16, timeout_s=timeout_s, lane="preflight")
        return {
            "ok": True,
            "reply": raw.text.strip()[:80],
            "served_model": raw.model,
            "claude_cli_version": self.cli_version(),
            "usage_available": raw.usage_available,
            "input_tokens_incl_cache": raw.input_tokens + raw.cache_read_input_tokens + raw.cache_creation_input_tokens,
            "output_tokens": raw.output_tokens,
            "auxiliary_input_tokens": raw.auxiliary_input_tokens,
            "cli_reported_cost_usd": raw.reported_cost_usd,
        }
