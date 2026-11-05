from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from outputguard._inputs import require_schema, text_sequence
from outputguard.configuration import attempt_limit, select_format
from outputguard.guard import OutputGuard
from outputguard.models import RepairResult, Schema, ValidationResult
from outputguard.strategies import select_strategy_names


@dataclass
class IndexedValidationResult(ValidationResult):
    index: int = 0
    input: str = ""


@dataclass
class IndexedRepairResult(RepairResult):
    index: int = 0
    input: str = ""


@dataclass
class BatchSummary:
    total: int
    valid: int
    invalid: int
    repaired: int
    parse_failures: int
    schema_failures: int
    success_rate: float
    strategy_counts: dict[str, int] = field(default_factory=dict)
    formats: dict[str, int] = field(default_factory=dict)


@dataclass
class BatchValidationResult:
    results: list[IndexedValidationResult]
    summary: BatchSummary


@dataclass
class BatchRepairResult:
    results: list[IndexedRepairResult]
    summary: BatchSummary


def validate_batch(
    texts: Sequence[str],
    schema: Schema,
    *,
    format: str | None = None,
    repair: bool = False,
    guard: OutputGuard | None = None,
) -> BatchValidationResult:
    active_guard = guard if guard is not None else OutputGuard()
    data_format = select_format(format, active_guard.format)
    require_schema(schema)
    if repair:
        attempt_limit(active_guard.max_repair_attempts, "max_repair_attempts")
        select_strategy_names(active_guard.strategies)
    results: list[IndexedValidationResult] = []
    for index, text in enumerate(text_sequence(texts)):
        result = (
            active_guard.validate_and_repair(text, schema, data_format)
            if repair
            else active_guard.validate(text, schema, data_format)
        )
        results.append(IndexedValidationResult(**result.__dict__, index=index, input=text))

    return BatchValidationResult(results=results, summary=_summarize_validation(results))


def repair_batch(
    texts: Sequence[str], *, format: str | None = None, guard: OutputGuard | None = None
) -> BatchRepairResult:
    active_guard = guard if guard is not None else OutputGuard()
    data_format = select_format(format, active_guard.format)
    select_strategy_names(active_guard.strategies)
    results: list[IndexedRepairResult] = []
    for index, text in enumerate(text_sequence(texts)):
        result = active_guard.repair(text, format=data_format)
        results.append(IndexedRepairResult(**result.__dict__, index=index, input=text))

    return BatchRepairResult(results=results, summary=_summarize_repairs(results))


def _summarize_validation(results: list[IndexedValidationResult]) -> BatchSummary:
    total = len(results)
    valid = repaired = parse_failures = 0
    strategy_counts: dict[str, int] = {}
    formats: dict[str, int] = {}
    # Custom guards may share metadata; count it after every result is collected.
    for result in results:
        valid += result.valid
        repaired += result.repaired
        parse_failures += result.parse_error is not None
        for strategy in result.strategies_applied:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        formats[result.format] = formats.get(result.format, 0) + 1
    invalid = total - valid
    return BatchSummary(
        total=total,
        valid=valid,
        invalid=invalid,
        repaired=repaired,
        parse_failures=parse_failures,
        schema_failures=invalid - parse_failures,
        success_rate=_success_rate(valid, total),
        strategy_counts=strategy_counts,
        formats=formats,
    )


def _summarize_repairs(results: list[IndexedRepairResult]) -> BatchSummary:
    total = len(results)
    valid = repaired = 0
    strategy_counts: dict[str, int] = {}
    formats: dict[str, int] = {}
    for result in results:
        valid += result.parse_error is None
        repaired += result.repaired
        for strategy in result.strategies_applied:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        formats[result.format] = formats.get(result.format, 0) + 1
    invalid = total - valid
    return BatchSummary(
        total=total,
        valid=valid,
        invalid=invalid,
        repaired=repaired,
        parse_failures=invalid,
        schema_failures=0,
        success_rate=_success_rate(valid, total),
        strategy_counts=strategy_counts,
        formats=formats,
    )


def _success_rate(valid: int, total: int) -> float:
    if total == 0:
        return 0.0
    # Round the exact count ratio half up, consistently with the JavaScript API.
    return ((valid * 2000 + total) // (2 * total)) / 1000
