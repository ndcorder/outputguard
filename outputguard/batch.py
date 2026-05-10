from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from outputguard.guard import OutputGuard
from outputguard.models import RepairResult, ValidationResult


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
    texts: list[str],
    schema: dict,
    *,
    format: str = "json",
    repair: bool = False,
    guard: OutputGuard | None = None,
) -> BatchValidationResult:
    active_guard = guard or OutputGuard(format=format)
    results: list[IndexedValidationResult] = []
    for index, text in enumerate(texts):
        result = (
            active_guard.validate_and_repair(text, schema, format)
            if repair
            else active_guard.validate(text, schema, format)
        )
        results.append(IndexedValidationResult(**result.__dict__, index=index, input=text))

    return BatchValidationResult(results=results, summary=_summarize_validation(results))


def repair_batch(
    texts: list[str], *, format: str = "json", guard: OutputGuard | None = None
) -> BatchRepairResult:
    active_guard = guard or OutputGuard(format=format)
    results: list[IndexedRepairResult] = []
    for index, text in enumerate(texts):
        result = active_guard.repair(text, format=format)
        results.append(IndexedRepairResult(**result.__dict__, index=index, input=text))

    return BatchRepairResult(results=results, summary=_summarize_repairs(results))


def _summarize_validation(results: list[IndexedValidationResult]) -> BatchSummary:
    total = len(results)
    valid = sum(result.valid for result in results)
    repaired = sum(result.repaired for result in results)
    parse_failures = sum((not result.valid) and result.data is None for result in results)
    invalid = total - valid
    return BatchSummary(
        total=total,
        valid=valid,
        invalid=invalid,
        repaired=repaired,
        parse_failures=parse_failures,
        schema_failures=invalid - parse_failures,
        success_rate=_success_rate(valid, total),
        strategy_counts=_count_strategies(results),
        formats=_count_formats(results),
    )


def _summarize_repairs(results: list[IndexedRepairResult]) -> BatchSummary:
    total = len(results)
    valid = sum(result.parse_error is None for result in results)
    repaired = sum(result.repaired for result in results)
    invalid = total - valid
    return BatchSummary(
        total=total,
        valid=valid,
        invalid=invalid,
        repaired=repaired,
        parse_failures=invalid,
        schema_failures=0,
        success_rate=_success_rate(valid, total),
        strategy_counts=_count_strategies(results),
        formats=_count_formats(results),
    )


def _count_strategies(results: Sequence[ValidationResult | RepairResult]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for result in results:
        counts.update(result.strategies_applied)
    return dict(counts)


def _count_formats(results: Sequence[ValidationResult | RepairResult]) -> dict[str, int]:
    counts: Counter[str] = Counter(result.format for result in results)
    return dict(counts)


def _success_rate(valid: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(valid / total, 3)
