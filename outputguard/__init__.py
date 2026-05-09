from outputguard.guard import OutputGuard
from outputguard.models import ValidationResult, RepairResult, ValidationError

_default_guard = OutputGuard()


def validate(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate(text, schema)


def repair(text: str) -> RepairResult:
    return _default_guard.repair(text)


def validate_and_repair(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate_and_repair(text, schema)


def retry_prompt(text: str, schema: dict, errors: list[ValidationError]) -> str:
    return _default_guard.retry_prompt(text, schema, errors)


__all__ = [
    "OutputGuard",
    "ValidationResult",
    "RepairResult",
    "ValidationError",
    "validate",
    "repair",
    "validate_and_repair",
    "retry_prompt",
]
