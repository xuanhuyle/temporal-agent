"""Application settings.

Settings are read from ``config/settings.json`` and validated strictly: every
key must be present, unknown keys are rejected, and values are type-checked.
Keyword overrides (used by tests and local tooling) go through the same
validation as the file contents.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_type_hints

DEFAULT_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.json"


@dataclass(frozen=True)
class Settings:
    database_path: str
    pbkdf2_iterations: int
    session_ttl_hours: int
    reconcile_interval_minutes: int
    checkout_grace_minutes: int
    paygate_api_base: str


_FIELD_TYPES: dict[str, type] = get_type_hints(Settings)


def _validate(key: str, value: Any) -> Any:
    expected = _FIELD_TYPES[key]
    if expected is int:
        # bool is a subclass of int; "true" is never a valid iteration count.
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"setting {key!r} must be an integer, got {value!r}")
        if value <= 0:
            raise ValueError(f"setting {key!r} must be positive, got {value!r}")
        return value
    if not isinstance(value, str) or not value:
        raise ValueError(f"setting {key!r} must be a non-empty string, got {value!r}")
    return value


def load_settings(path: str | Path | None = None, **overrides: Any) -> Settings:
    """Load settings from ``path`` (default: the shipped settings file).

    ``overrides`` replace individual values after the file is read.

    Raises:
        ValueError: if the file or overrides contain unknown keys, a key is
            missing, or a value has the wrong type.
    """
    settings_path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
    with settings_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{settings_path} must contain a JSON object")

    known = set(_FIELD_TYPES)
    unknown = (set(raw) | set(overrides)) - known
    if unknown:
        raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")

    merged = {**raw, **overrides}
    missing = known - set(merged)
    if missing:
        raise ValueError(f"missing setting(s): {', '.join(sorted(missing))}")

    return Settings(**{key: _validate(key, merged[key]) for key in _FIELD_TYPES})
