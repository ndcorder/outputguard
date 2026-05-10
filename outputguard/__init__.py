from outputguard.batch import (
    BatchRepairResult,
    BatchSummary,
    BatchValidationResult,
    IndexedRepairResult,
    IndexedValidationResult,
    repair_batch,
    validate_batch,
)
from outputguard.exceptions import (
    OutputGuardError,
    ParseError,
    RepairError,
    SchemaValidationError,
    StrategyError,
)
from outputguard.formats import SUPPORTED_FORMATS
from outputguard.generation import (
    GuardedGenerateAttempt,
    GuardedGenerateContext,
    GuardedGenerateResult,
    GuardedGenerationError,
    guarded_generate,
    guarded_generate_async,
)
from outputguard.guard import OutputGuard
from outputguard.models import RepairResult, ValidationError, ValidationResult
from outputguard.report import RepairReport, StrategyApplication

_default_guard = OutputGuard()


def validate(text: str, schema: dict, format: str = "json") -> ValidationResult:
    return _default_guard.validate(text, schema, format=format)


def repair(text: str, format: str = "json") -> RepairResult:
    return _default_guard.repair(text, format=format)  # type: ignore[return-value]


def validate_and_repair(text: str, schema: dict, format: str = "json") -> ValidationResult:
    return _default_guard.validate_and_repair(text, schema, format=format)


def parse(text: str, schema: dict, format: str = "json"):
    """Validate, repair, and return parsed data. Raises on failure."""
    return _default_guard.parse(text, schema, format=format)


def retry_prompt(
    text: str, schema: dict, errors: list[ValidationError], format: str = "json"
) -> str:
    return _default_guard.retry_prompt(text, schema, errors, format=format)


__all__ = [
    "OutputGuard",
    "BatchRepairResult",
    "BatchSummary",
    "BatchValidationResult",
    "GuardedGenerateAttempt",
    "GuardedGenerateContext",
    "GuardedGenerateResult",
    "GuardedGenerationError",
    "IndexedRepairResult",
    "IndexedValidationResult",
    "OutputGuardError",
    "ParseError",
    "RepairError",
    "RepairReport",
    "RepairResult",
    "SUPPORTED_FORMATS",
    "SchemaValidationError",
    "StrategyApplication",
    "StrategyError",
    "ValidationError",
    "ValidationResult",
    "guarded_generate",
    "guarded_generate_async",
    "parse",
    "repair",
    "repair_batch",
    "retry_prompt",
    "validate",
    "validate_and_repair",
    "validate_batch",
]
