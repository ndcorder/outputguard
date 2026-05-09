from outputguard.exceptions import (
    OutputGuardError,
    ParseError,
    RepairError,
    SchemaValidationError,
    StrategyError,
)
from outputguard.guard import OutputGuard
from outputguard.models import RepairResult, ValidationError, ValidationResult
from outputguard.report import RepairReport, StrategyApplication

_default_guard = OutputGuard()


def validate(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate(text, schema)


def repair(text: str) -> RepairResult:
    return _default_guard.repair(text)  # type: ignore[return-value]


def validate_and_repair(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate_and_repair(text, schema)


def parse(text: str, schema: dict) -> dict | list:
    """Validate, repair, and return parsed data. Raises on failure."""
    return _default_guard.parse(text, schema)


def retry_prompt(text: str, schema: dict, errors: list[ValidationError]) -> str:
    return _default_guard.retry_prompt(text, schema, errors)


__all__ = [
    "OutputGuard",
    "OutputGuardError",
    "ParseError",
    "RepairError",
    "RepairReport",
    "RepairResult",
    "SchemaValidationError",
    "StrategyApplication",
    "StrategyError",
    "ValidationError",
    "ValidationResult",
    "parse",
    "repair",
    "retry_prompt",
    "validate",
    "validate_and_repair",
]
