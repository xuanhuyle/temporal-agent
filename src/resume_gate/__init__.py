"""Resume Gate: deterministic checkpoint validity checks for long-running agents."""

from .validator import Verdict, ValidationResult, validate_resume

__all__ = ["Verdict", "ValidationResult", "validate_resume"]
