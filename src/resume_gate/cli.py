from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .validator import Verdict, validate_resume


_EXIT = {
    Verdict.SAFE: 0,
    Verdict.REVALIDATE: 2,
    Verdict.MIGRATE: 3,
    Verdict.BLOCK: 4,
}


def _load(path: str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return data


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-gate",
        description="Validate whether a persisted agent checkpoint is still safe to resume.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser(
        "validate",
        help="compare a checkpoint manifest with the current runtime manifest",
    )
    validate.add_argument("checkpoint", help="checkpoint manifest JSON")
    validate.add_argument("current", help="current runtime manifest JSON")
    validate.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command != "validate":
        return 1
    try:
        checkpoint = _load(args.checkpoint)
        current = _load(args.current)
        result = validate_resume(checkpoint, current)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"resume-gate: {exc}")
        return 1

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(result.verdict.value)
        if not result.issues:
            print("No resume-invalidating drift detected.")
        for issue in result.issues:
            subject = f" [{issue.subject}]" if issue.subject else ""
            print(f"- {issue.verdict.value}: {issue.code}{subject}: {issue.message}")
    return _EXIT[result.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
