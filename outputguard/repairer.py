"""Structured-output repair engine — applies strategies in sequence to fix malformed data."""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from types import CoroutineType
from typing import Literal, overload

from outputguard._inputs import is_text
from outputguard.formats import FormatParseError, normalize_format, parse_document
from outputguard.models import RepairResult
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import Strategy, get_strategies, select_strategy_names


def _apply_strategy(name: str, fn: Strategy, text: str) -> StrategyApplication:
    """A faulty strategy cannot replace text with a non-string or abort later fixes."""
    try:
        output = fn(text)
        if not is_text(output):
            if (
                type(output) is CoroutineType
                and inspect.getcoroutinestate(output) == inspect.CORO_CREATED
            ):
                output.close()
            raise TypeError("Strategy must return a string")
        return StrategyApplication(name, output != text, text, output)
    except Exception as error:
        try:
            message = str(error) or type(error).__name__
        except Exception:
            message = "Strategy failed"
        return StrategyApplication(name, False, text, text, error=message)


@overload
def repair(
    text: str,
    strategies: Sequence[str] | None = ...,
    *,
    report: Literal[False] = False,
    format: str = ...,
) -> RepairResult: ...


@overload
def repair(
    text: str,
    strategies: Sequence[str] | None = ...,
    *,
    report: Literal[True],
    format: str = ...,
) -> tuple[RepairResult, RepairReport]: ...


@overload
def repair(
    text: str,
    strategies: Sequence[str] | None = ...,
    *,
    report: bool,
    format: str = ...,
) -> RepairResult | tuple[RepairResult, RepairReport]: ...


def repair(
    text: str,
    strategies: Sequence[str] | None = None,
    *,
    report: bool = False,
    format: str = "json",
) -> RepairResult | tuple[RepairResult, RepairReport]:
    """Apply repair strategies in order, try to parse after each one.

    If report=True, returns a (RepairResult, RepairReport) tuple.
    """
    selected = select_strategy_names(strategies)
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

    strategy_list = get_strategies(selected)
    last_error: str = ""
    steps: list[StrategyApplication] = []

    # Non-JSON formats should preserve their syntax when a single generic strategy
    # such as strip_fences is enough. JSON keeps the historical all-strategies
    # first pass because many existing repairs depend on accumulated fixes.
    if normalize_format(format) not in ("json", "auto"):
        current = text
        pre_applied: list[str] = []
        for name, fn in strategy_list:
            step = _apply_strategy(name, fn, current)
            steps.append(step)
            current = step.output_text
            if step.changed:
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
        step = _apply_strategy(name, fn, current)
        steps.append(step)
        current = step.output_text
        if step.changed:
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
        step = _apply_strategy(name, fn, current)
        steps.append(step)
        current = step.output_text
        if step.changed:
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
