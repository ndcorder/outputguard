"""Replace single-quoted strings with double-quoted in JSON-like text."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_quotes"
DESCRIPTION = "Replace single-quoted strings with double-quoted"

_OPEN = re.compile(r"[\"'/]")
_SPECIAL = re.compile(r"[\"'\\]")


def _single_quoted(text: str, start: int, pieces: list[str]) -> int:
    pieces.append('"')
    copied = index = start + 1
    while match := _SPECIAL.search(text, index):
        position = match.start()
        char = text[position]
        if char == "'":
            pieces.extend((text[copied:position], '"'))
            return position + 1
        if char == '"':
            pieces.extend((text[copied:position], '\\"'))
            copied = index = position + 1
        elif position + 1 == len(text):
            # Retain a final literal backslash before adding the closing quote.
            pieces.extend((text[copied:position], "\\\\"))
            copied = len(text)
            break
        else:
            if text[position + 1] == "'":
                pieces.extend((text[copied:position], "'"))
                copied = position + 2
            # Other escape pairs are retained for JSON or later escape repairs.
            index = position + 2
    pieces.extend((text[copied:], '"'))
    return len(text)


def apply(text: str) -> str:
    if "'" not in text:
        return text
    pieces: list[str] = []
    copied = index = 0
    while match := _OPEN.search(text, index):
        start = match.start()
        if text[start] == '"':
            index = quoted_end(text, start)
        elif text[start] == "/":
            if start + 1 < len(text) and text[start + 1] in "/*":
                index = comment_end(text, start)
            else:
                index = start + 1
        else:
            pieces.append(text[copied:start])
            copied = index = _single_quoted(text, start, pieces)
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
