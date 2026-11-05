"""Escape raw JSON control characters inside quoted strings."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_newlines"
DESCRIPTION = "Escape raw control characters inside quoted strings"

_CONTROL = re.compile(r"[\x00-\x1f]")
_OPEN = re.compile(r"[\"'/]")
_INSIDE = re.compile(r"\\[\s\S]|[\x00-\x1f]")
_SHORT = {8: r"\b", 9: r"\t", 10: r"\n", 12: r"\f", 13: r"\r"}
_ESCAPES = tuple(_SHORT.get(code, f"\\u{code:04x}") for code in range(32))


def _escape(match: re.Match[str]) -> str:
    token = match[0]
    if token[0] == "\\":
        code = ord(token[1])
        # An invalid backslash/control pair retains both literal characters.
        return "\\\\" + _ESCAPES[code] if code < 32 else token
    return _ESCAPES[ord(token)]


def apply(text: str) -> str:
    if not _CONTROL.search(text):
        return text
    pieces: list[str] = []
    copied = index = 0
    while match := _OPEN.search(text, index):
        start = match.start()
        if text[start] == "/":
            if start + 1 < len(text) and text[start + 1] in "/*":
                index = comment_end(text, start)
            else:
                index = start + 1
            continue
        end = quoted_end(text, start)
        if _CONTROL.search(text, start, end):
            pieces.extend((text[copied:start], _INSIDE.sub(_escape, text[start:end])))
            copied = end
        index = end
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
