"""Structured-output repair engine — applies strategies in sequence to fix malformed data."""

from __future__ import annotations

from typing import Literal, overload

from outputguard.formats import FormatParseError, normalize_format, parse_document
from outputguard.models import RepairResult
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import get_strategies


@overload
def repair(text: str, strategies: list[str] | None = ..., *, format: str = ...) -> RepairResult: ...


@overload
def repair(
    text: str,
    strategies: list[str] | None = ...,
    *,
    report: Literal[True],
    format: str = ...,
) -> tuple[RepairResult, RepairReport]: ...


def repair(
    text: str, strategies: list[str] | None = None, *, report: bool = False, format: str = "json"
) -> RepairResult | tuple[RepairResult, RepairReport]:
    """Apply repair strategies in order, try to parse after each one.

    If report=True, returns a (RepairResult, RepairReport) tuple.
    """
    try:
        parse_document(text, format)
        result = RepairResult(repaired=False, text=text, format=format)
        if report:
            return result, RepairReport(
                original_text=text, final_text=text, success=True, format=format
            )
        return result
    except FormatParseError:
        pass

    strategy_list = get_strategies(strategies)
    last_error: str = ""
    steps: list[StrategyApplication] = []

    # Non-JSON formats should preserve their syntax when a single generic strategy
    # such as strip_fences is enough. JSON keeps the historical all-strategies
    # first pass because many existing repairs depend on accumulated fixes.
    if normalize_format(format) not in ("json", "auto"):
        current = text
        pre_applied: list[str] = []
        for name, fn in strategy_list:
            before = current
            try:
                current = fn(current)
            except Exception:
                current = before
            changed = current != before
            steps.append(
                StrategyApplication(
                    name=name, changed=changed, input_text=before, output_text=current
                )
            )
            if changed:
                pre_applied.append(name)
            try:
                parse_document(current, format)
                result = RepairResult(
                    repaired=True, text=current, strategies_applied=pre_applied, format=format
                )
                if report:
                    return result, RepairReport(
                        original_text=text,
                        final_text=current,
                        success=True,
                        steps=steps,
                        format=format,
                    )
                return result
            except FormatParseError as e:
                last_error = str(e)
        steps = []
        last_error = ""

    # First pass: apply ALL strategies in sequence, then try parsing
    current = text
    applied: list[str] = []
    for name, fn in strategy_list:
        before = current
        try:
            current = fn(current)
        except Exception:
            current = before
        changed = current != before
        steps.append(
            StrategyApplication(name=name, changed=changed, input_text=before, output_text=current)
        )
        if changed:
            applied.append(name)

    try:
        parse_document(current, format)
        result = RepairResult(
            repaired=True, text=current, strategies_applied=applied, format=format
        )
        if report:
            return result, RepairReport(
                original_text=text, final_text=current, success=True, steps=steps, format=format
            )
        return result
    except FormatParseError as e:
        last_error = str(e)

    # Second pass: apply one at a time with parse attempts between each
    current = text
    applied = []
    steps = []
    for name, fn in strategy_list:
        before = current
        try:
            current = fn(current)
        except Exception:
            current = before
        changed = current != before
        steps.append(
            StrategyApplication(name=name, changed=changed, input_text=before, output_text=current)
        )
        if changed:
            applied.append(name)
        try:
            parse_document(current, format)
            result = RepairResult(
                repaired=True, text=current, strategies_applied=applied, format=format
            )
            if report:
                return result, RepairReport(
                    original_text=text, final_text=current, success=True, steps=steps, format=format
                )
            return result
        except FormatParseError as e:
            last_error = str(e)

    result = RepairResult(repaired=False, text=text, parse_error=last_error, format=format)
    if report:
        return result, RepairReport(
            original_text=text,
            final_text=text,
            success=False,
            steps=steps,
            parse_error=last_error,
            format=format,
        )
    return result
