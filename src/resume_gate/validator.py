from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable


class Verdict(str, Enum):
    SAFE = "SAFE"
    REVALIDATE = "REVALIDATE"
    MIGRATE = "MIGRATE"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class Issue:
    code: str
    verdict: Verdict
    message: str
    subject: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data


@dataclass(frozen=True)
class ValidationResult:
    verdict: Verdict
    issues: tuple[Issue, ...]
    checkpoint_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "checkpoint_id": self.checkpoint_id,
            "issues": [issue.to_dict() for issue in self.issues],
        }


_RANK = {
    Verdict.SAFE: 0,
    Verdict.REVALIDATE: 1,
    Verdict.MIGRATE: 2,
    Verdict.BLOCK: 3,
}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _index(items: Iterable[dict[str, Any]], key: str = "id") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        identifier = item.get(key)
        if identifier is not None:
            out[str(identifier)] = item
    return out


def _issue(
    issues: list[Issue],
    code: str,
    verdict: Verdict,
    message: str,
    subject: str | None = None,
) -> None:
    issues.append(Issue(code=code, verdict=verdict, message=message, subject=subject))


def validate_resume(checkpoint: dict[str, Any], current: dict[str, Any]) -> ValidationResult:
    """Compare checkpoint assumptions with the current execution environment.

    The gate is deliberately deterministic. It does not infer hidden dependencies;
    it checks only facts explicitly declared in the checkpoint manifest.
    """

    issues: list[Issue] = []
    cp_runtime = checkpoint.get("runtime") or {}
    now_runtime = current.get("runtime") or {}

    cp_schema = cp_runtime.get("state_schema")
    now_schema = now_runtime.get("state_schema")
    if cp_schema != now_schema:
        _issue(
            issues,
            "STATE_SCHEMA_CHANGED",
            Verdict.MIGRATE,
            f"Checkpoint state schema {cp_schema!r} differs from current schema {now_schema!r}.",
            "runtime.state_schema",
        )

    cp_agent = cp_runtime.get("agent_version")
    now_agent = now_runtime.get("agent_version")
    if cp_agent != now_agent:
        _issue(
            issues,
            "AGENT_VERSION_CHANGED",
            Verdict.REVALIDATE,
            f"Agent version changed from {cp_agent!r} to {now_agent!r}.",
            "runtime.agent_version",
        )

    cp_model = cp_runtime.get("model")
    now_model = now_runtime.get("model")
    if cp_model != now_model:
        _issue(
            issues,
            "MODEL_CHANGED",
            Verdict.REVALIDATE,
            f"Model changed from {cp_model!r} to {now_model!r}.",
            "runtime.model",
        )

    cp_policy = checkpoint.get("policy_version")
    now_policy = current.get("policy_version")
    if cp_policy != now_policy:
        _issue(
            issues,
            "POLICY_CHANGED",
            Verdict.REVALIDATE,
            f"Policy version changed from {cp_policy!r} to {now_policy!r}.",
            "policy_version",
        )

    cp_tools = checkpoint.get("tools") or {}
    now_tools = current.get("tools") or {}
    for name, cp_tool in cp_tools.items():
        now_tool = now_tools.get(name)
        if now_tool is None:
            _issue(
                issues,
                "TOOL_REMOVED",
                Verdict.BLOCK,
                f"Tool {name!r} existed at checkpoint time but is no longer available.",
                f"tools.{name}",
            )
            continue
        if cp_tool.get("version") != now_tool.get("version"):
            _issue(
                issues,
                "TOOL_VERSION_CHANGED",
                Verdict.REVALIDATE,
                f"Tool {name!r} changed version from {cp_tool.get('version')!r} to {now_tool.get('version')!r}.",
                f"tools.{name}",
            )
        if cp_tool.get("permission") != now_tool.get("permission"):
            _issue(
                issues,
                "TOOL_PERMISSION_CHANGED",
                Verdict.BLOCK,
                f"Tool {name!r} no longer has the same permission contract.",
                f"tools.{name}.permission",
            )

    now_dt = _parse_time(current.get("now"))
    cp_authorities = _index(checkpoint.get("authorities") or [])
    now_authorities = _index(current.get("authorities") or [])
    for authority_id, cp_auth in cp_authorities.items():
        now_auth = now_authorities.get(authority_id)
        subject = f"authorities.{authority_id}"
        if now_auth is None:
            _issue(
                issues,
                "AUTHORITY_MISSING",
                Verdict.BLOCK,
                f"Authority {authority_id!r} from the checkpoint is not present in the current authority set.",
                subject,
            )
            continue
        if now_auth.get("status", "active") != "active":
            _issue(
                issues,
                "AUTHORITY_NOT_ACTIVE",
                Verdict.BLOCK,
                f"Authority {authority_id!r} is currently {now_auth.get('status')!r}, not active.",
                subject,
            )
        if cp_auth.get("scope") != now_auth.get("scope"):
            _issue(
                issues,
                "AUTHORITY_SCOPE_CHANGED",
                Verdict.BLOCK,
                f"Authority {authority_id!r} scope changed from {cp_auth.get('scope')!r} to {now_auth.get('scope')!r}.",
                subject,
            )
        expires_at = _parse_time(now_auth.get("expires_at"))
        if now_dt is not None and expires_at is not None and expires_at <= now_dt:
            _issue(
                issues,
                "AUTHORITY_EXPIRED",
                Verdict.BLOCK,
                f"Authority {authority_id!r} expired at {now_auth.get('expires_at')}.",
                subject,
            )
        if cp_auth.get("policy_version") != now_auth.get("policy_version"):
            _issue(
                issues,
                "AUTHORITY_POLICY_CHANGED",
                Verdict.REVALIDATE,
                f"Authority {authority_id!r} was granted under a different policy version.",
                subject,
            )

    cp_dependencies = _index(checkpoint.get("dependencies") or [])
    now_dependencies = _index(current.get("dependencies") or [])
    for dep_id, cp_dep in cp_dependencies.items():
        now_dep = now_dependencies.get(dep_id)
        subject = f"dependencies.{dep_id}"
        if now_dep is None:
            _issue(
                issues,
                "DEPENDENCY_MISSING",
                Verdict.REVALIDATE,
                f"Dependency {dep_id!r} cannot be verified in the current environment.",
                subject,
            )
            continue
        if cp_dep.get("version") != now_dep.get("version"):
            _issue(
                issues,
                "DEPENDENCY_CHANGED",
                Verdict.REVALIDATE,
                f"Dependency {dep_id!r} changed from {cp_dep.get('version')!r} to {now_dep.get('version')!r}.",
                subject,
            )
        max_age = cp_dep.get("max_age_seconds")
        observed_at = _parse_time(now_dep.get("observed_at"))
        if max_age is not None and now_dt is not None and observed_at is not None:
            age = (now_dt - observed_at).total_seconds()
            if age > float(max_age):
                _issue(
                    issues,
                    "DEPENDENCY_STALE",
                    Verdict.REVALIDATE,
                    f"Dependency {dep_id!r} is {int(age)}s old, beyond the declared {max_age}s freshness window.",
                    subject,
                )

    for effect in checkpoint.get("side_effects") or []:
        effect_id = str(effect.get("id", "<unknown>"))
        status = effect.get("status")
        subject = f"side_effects.{effect_id}"
        if status in {"pending", "unknown"}:
            if effect.get("idempotency_key"):
                _issue(
                    issues,
                    "SIDE_EFFECT_UNCERTAIN",
                    Verdict.REVALIDATE,
                    f"Side effect {effect_id!r} may already have executed; verify its receipt before retrying.",
                    subject,
                )
            else:
                _issue(
                    issues,
                    "NON_IDEMPOTENT_SIDE_EFFECT_UNCERTAIN",
                    Verdict.BLOCK,
                    f"Side effect {effect_id!r} is uncertain and has no idempotency key; automatic replay is unsafe.",
                    subject,
                )
        elif status == "committed" and not effect.get("receipt"):
            _issue(
                issues,
                "COMMITTED_SIDE_EFFECT_WITHOUT_RECEIPT",
                Verdict.REVALIDATE,
                f"Side effect {effect_id!r} is marked committed but has no durable receipt.",
                subject,
            )

    verdict = Verdict.SAFE
    for issue in issues:
        if _RANK[issue.verdict] > _RANK[verdict]:
            verdict = issue.verdict

    return ValidationResult(
        verdict=verdict,
        issues=tuple(issues),
        checkpoint_id=checkpoint.get("checkpoint_id"),
    )
