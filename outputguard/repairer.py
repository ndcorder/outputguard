"""JSON repair engine — applies strategies in sequence to fix malformed JSON."""

import json

from outputguard.models import RepairResult
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import get_strategies


def repair(
    text: str, strategies: list[str] | None = None, report: bool = False
) -> RepairResult | tuple[RepairResult, RepairReport]:
    """Apply repair strategies in order, try to parse after each one.

    If report=True, returns a (RepairResult, RepairReport) tuple.
    """
    try:
        json.loads(text)
        result = RepairResult(repaired=False, text=text)
        if report:
            return result, RepairReport(
                original_text=text, final_text=text, success=True
            )
        return result
    except json.JSONDecodeError:
        pass

    strategy_list = get_strategies(strategies)
    last_error: str = ""
    steps: list[StrategyApplication] = []

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
        steps.append(StrategyApplication(
            name=name, changed=changed, input_text=before, output_text=current
        ))
        if changed:
            applied.append(name)

    try:
        json.loads(current)
        result = RepairResult(
            repaired=True, text=current, strategies_applied=applied
        )
        if report:
            return result, RepairReport(
                original_text=text, final_text=current, success=True, steps=steps
            )
        return result
    except json.JSONDecodeError as e:
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
        steps.append(StrategyApplication(
            name=name, changed=changed, input_text=before, output_text=current
        ))
        if changed:
            applied.append(name)
        try:
            json.loads(current)
            result = RepairResult(
                repaired=True, text=current, strategies_applied=applied
            )
            if report:
                return result, RepairReport(
                    original_text=text, final_text=current, success=True, steps=steps
                )
            return result
        except json.JSONDecodeError as e:
            last_error = str(e)

    result = RepairResult(repaired=False, text=text, parse_error=last_error)
    if report:
        return result, RepairReport(
            original_text=text, final_text=text, success=False,
            steps=steps, parse_error=last_error
        )
    return result
