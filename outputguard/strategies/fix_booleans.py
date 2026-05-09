"""Replace Python-style booleans and None with JSON equivalents."""

import re

NAME = "fix_booleans"
DESCRIPTION = "Replace Python True/False/None with true/false/null"

_PATTERNS = [
    (re.compile(r"\bTrue\b"), "true"),
    (re.compile(r"\bFalse\b"), "false"),
    (re.compile(r"\bNone\b"), "null"),
]


def _count_unescaped_quotes(text: str, end: int) -> int:
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
        matches = list(pattern.finditer(text))
        for m in reversed(matches):
            if _count_unescaped_quotes(text, m.start()) % 2 == 0:
                text = text[: m.start()] + replacement + text[m.end() :]
    return text
