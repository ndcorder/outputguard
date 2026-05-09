"""JSON repair engine — applies strategies in sequence to fix malformed JSON."""

import json

from outputguard.models import RepairResult
from outputguard.strategies import get_strategies


def repair(text: str, strategies: list[str] | None = None) -> RepairResult:
    """Apply repair strategies in order, try to parse after each one."""
    # Already valid — nothing to do
    try:
        json.loads(text)
        return RepairResult(repaired=False, text=text)
    except json.JSONDecodeError:
        pass

    strategy_list = get_strategies(strategies)
    last_error: str = ""

    # --- First pass: apply ALL strategies in sequence, then try parsing ---
    current = text
    applied: list[str] = []
    for name, fn in strategy_list:
        before = current
        try:
            current = fn(current)
        except Exception:
            continue
        if current != before:
            applied.append(name)

    try:
        json.loads(current)
        return RepairResult(repaired=True, text=current, strategies_applied=applied)
    except json.JSONDecodeError as e:
        last_error = str(e)

    # --- Second pass: apply one at a time with parse attempts between each ---
    current = text
    applied = []
    for name, fn in strategy_list:
        before = current
        try:
            current = fn(current)
        except Exception:
            continue
        if current != before:
            applied.append(name)
        try:
            json.loads(current)
            return RepairResult(repaired=True, text=current, strategies_applied=applied)
        except json.JSONDecodeError as e:
            last_error = str(e)

    return RepairResult(repaired=False, text=text, parse_error=last_error)
