from typing import Literal, overload

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
    SchemaEvaluationError,
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
from outputguard.models import RepairResult, Schema, ValidationError, ValidationResult
from outputguard.report import RepairReport, StrategyApplication
from outputguard.validator import invalidate_schema

_default_guard = OutputGuard()


def validate(text: str, schema: Schema, format: str | None = "json") -> ValidationResult:
    return _default_guard.validate(text, schema, format=format)


@overload
def repair(
    text: str, format: str | None = "json", *, report: Literal[False] = False
) -> RepairResult: ...


@overload
def repair(
    text: str, format: str | None = "json", *, report: Literal[True]
) -> tuple[RepairResult, RepairReport]: ...


@overload
def repair(
    text: str, format: str | None = "json", *, report: bool
) -> RepairResult | tuple[RepairResult, RepairReport]: ...


def repair(
    text: str, format: str | None = "json", *, report: bool = False
) -> RepairResult | tuple[RepairResult, RepairReport]:
    """Repair syntax, optionally returning the result and its detailed report."""
    return _default_guard.repair(text, format=format, report=report)


def validate_and_repair(text: str, schema: Schema, format: str | None = "json") -> ValidationResult:
    return _default_guard.validate_and_repair(text, schema, format=format)


def parse(text: str, schema: Schema, format: str | None = "json"):
    """Validate, repair, and return parsed data. Raises on failure."""
    return _default_guard.parse(text, schema, format=format)


def retry_prompt(
    text: str,
    schema: Schema,
    errors: list[ValidationError],
    format: str | None = "json",
    include_message_history: bool = True,
) -> str:
    return _default_guard.retry_prompt(
        text,
        schema,
        errors,
        format=format,
        include_message_history=include_message_history,
    )


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
    "Schema",
    "SchemaEvaluationError",
    "SchemaValidationError",
    "StrategyApplication",
    "StrategyError",
    "ValidationError",
    "ValidationResult",
    "guarded_generate",
    "guarded_generate_async",
    "invalidate_schema",
    "parse",
    "repair",
    "repair_batch",
    "retry_prompt",
    "validate",
    "validate_and_repair",
    "validate_batch",
]
