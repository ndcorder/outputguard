"""Deterministic unified diffs with bounded matching work and LF-based lines."""

import json
import re
from typing import NamedTuple

_CONTEXT = 3
_MAX_DISTANCE = 256
_MAX_WORK = 1_000_000


class _Op(NamedTuple):
    equal: bool
    a0: int
    a1: int
    b0: int
    b1: int


def _lines(text: str) -> list[str]:
    lines = []
    start = 0
    while start < len(text):
        end = text.find("\n", start)
        if end == -1:
            lines.append(text[start:])
            break
        lines.append(text[start : end + 1])
        start = end + 1
    return lines


def _matching_ops(a: list[int], b: list[int], start: int) -> list[_Op]:
    n, m = len(a), len(b)
    fallback = [_Op(False, start, start + n, start, start + m)]
    if not n or not m or abs(n - m) > _MAX_DISTANCE:
        return fallback
    trace: list[list[int]] = []
    work = 0
    for depth in range(min(n + m, _MAX_DISTANCE) + 1):
        frontier = [-1] * (2 * depth + 1)
        for diagonal in range(-depth, depth + 1, 2):
            work += 1
            if work > _MAX_WORK:
                return fallback
            if depth == 0:
                x = 0
            elif diagonal == -depth or (
                diagonal != depth and trace[-1][diagonal + depth - 2] < trace[-1][diagonal + depth]
            ):
                x = trace[-1][diagonal + depth]
            else:
                x = trace[-1][diagonal + depth - 2] + 1
            y = x - diagonal
            while x < n and y < m:
                work += 1
                if work > _MAX_WORK:
                    return fallback
                if a[x] != b[y]:
                    break
                x += 1
                y += 1
            frontier[diagonal + depth] = x
            if x >= n and y >= m:
                trace.append(frontier)
                return _backtrack(trace, n, m, start)
        trace.append(frontier)
    return fallback


def _backtrack(trace: list[list[int]], x: int, y: int, start: int) -> list[_Op]:
    reversed_ops = []
    for depth in range(len(trace) - 1, 0, -1):
        diagonal = x - y
        previous = trace[depth - 1]
        if diagonal == -depth or (
            diagonal != depth and previous[diagonal + depth - 2] < previous[diagonal + depth]
        ):
            px = previous[diagonal + depth]
            py = px - diagonal - 1
            ax, ay = px, py + 1
        else:
            px = previous[diagonal + depth - 2]
            py = px - diagonal + 1
            ax, ay = px + 1, py
        if x > ax:
            reversed_ops.append(_Op(True, ax, x, ay, y))
        reversed_ops.append(_Op(False, px, ax, py, ay))
        x, y = px, py
    if x:
        reversed_ops.append(_Op(True, 0, x, 0, y))
    result: list[_Op] = []
    for op in reversed(reversed_ops):
        shifted = _Op(op.equal, op.a0 + start, op.a1 + start, op.b0 + start, op.b1 + start)
        if result and result[-1].equal == op.equal:
            previous_op = result[-1]
            result[-1] = _Op(op.equal, previous_op.a0, shifted.a1, previous_op.b0, shifted.b1)
        else:
            result.append(shifted)
    return result


def _middle_ops(
    a_lines: list[str], b_lines: list[str], start: int, a_end: int, b_end: int
) -> list[_Op]:
    n, m = a_end - start, b_end - start
    if not n or not m or (n == 1 and m == 1) or abs(n - m) > _MAX_DISTANCE:
        return [_Op(False, start, a_end, start, b_end)]

    identifiers: dict[str, int] = {}
    a = []
    for i in range(start, a_end):
        line = a_lines[i]
        identifier = identifiers.get(line)
        if identifier is None:
            identifier = len(identifiers)
            identifiers[line] = identifier
        a.append(identifier)
    # New-only lines cannot match any old line and can share the sentinel -1.
    # Keep identifier zero distinct from that sentinel.
    b = [identifiers.get(b_lines[i], -1) for i in range(start, b_end)]
    if not any(identifier >= 0 for identifier in b):
        return [_Op(False, start, a_end, start, b_end)]
    return _matching_ops(a, b, start)


def _ops(a_lines: list[str], b_lines: list[str]) -> list[_Op]:
    start, a_end, b_end = 0, len(a_lines), len(b_lines)
    prefix_limit = min(a_end, b_end)
    while start < prefix_limit and a_lines[start] == b_lines[start]:
        start += 1
    while a_end > start and b_end > start and a_lines[a_end - 1] == b_lines[b_end - 1]:
        a_end -= 1
        b_end -= 1
    result = [_Op(True, 0, start, 0, start)] if start else []
    result.extend(_middle_ops(a_lines, b_lines, start, a_end, b_end))
    if a_end < len(a_lines):
        result.append(_Op(True, a_end, len(a_lines), b_end, len(b_lines)))
    return result


def _groups(ops: list[_Op]) -> list[list[_Op]]:
    if ops[0].equal:
        op = ops[0]
        ops[0] = _Op(True, max(op.a0, op.a1 - _CONTEXT), op.a1, max(op.b0, op.b1 - _CONTEXT), op.b1)
    if ops[-1].equal:
        op = ops[-1]
        ops[-1] = _Op(
            True, op.a0, min(op.a1, op.a0 + _CONTEXT), op.b0, min(op.b1, op.b0 + _CONTEXT)
        )
    groups, current = [], []
    for op in ops:
        if op.equal and op.a1 - op.a0 > 2 * _CONTEXT:
            current.append(_Op(True, op.a0, op.a0 + _CONTEXT, op.b0, op.b0 + _CONTEXT))
            groups.append(current)
            current = [_Op(True, op.a1 - _CONTEXT, op.a1, op.b1 - _CONTEXT, op.b1)]
        else:
            current.append(op)
    groups.append(current)
    return groups


def _range(start: int, end: int) -> str:
    count = end - start
    if count == 1:
        return str(start + 1)
    return f"{start + 1 if count else start},{count}"


def _label(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z0-9_./-]+", value) else json.dumps(value)


def unified_diff(before: str, after: str, fromfile: str, tofile: str) -> str:
    """Return an LF-terminated patch; preserve payload CRs and missing final LFs."""
    if before == after:
        return ""
    a, b = _lines(before), _lines(after)
    parts = [f"--- {_label(fromfile)}\n", f"+++ {_label(tofile)}\n"]

    def emit(prefix, line):
        parts.append(prefix + line)
        if not line.endswith("\n"):
            parts.append("\n\\ No newline at end of file\n")

    for group in _groups(_ops(a, b)):
        parts.append(
            f"@@ -{_range(group[0].a0, group[-1].a1)} +{_range(group[0].b0, group[-1].b1)} @@\n"
        )
        for op in group:
            for i in range(op.a0, op.a1):
                emit(" " if op.equal else "-", a[i])
            if not op.equal:
                for i in range(op.b0, op.b1):
                    emit("+", b[i])
    return "".join(parts)
