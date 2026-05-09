"""Replace JavaScript-specific values with JSON-compatible equivalents."""

import re

NAME = "fix_values"

_PATTERNS = [
    (re.compile(r"-Infinity"), "null"),
    (re.compile(r"\bInfinity\b"), "null"),
    (re.compile(r"\bNaN\b"), "null"),
    (re.compile(r"\bundefined\b"), "null"),
]


def _count_unescaped_quotes(text: str, end: int) -> int:
    """Count unescaped double quotes in text[:end]."""
    count = 0
    i = 0
    while i < end:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            count += 1
        i += 1
    return count


def apply(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        # Process matches from right to left so indices stay valid
        matches = list(pattern.finditer(text))
        for m in reversed(matches):
            # If the number of unescaped quotes before this match is even,
            # we're outside a string.
            if _count_unescaped_quotes(text, m.start()) % 2 == 0:
                text = text[: m.start()] + replacement + text[m.end() :]
    return text
