"""Add double quotes to unquoted object keys."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_keys"
DESCRIPTION = "Add double quotes to unquoted object keys"

_NAME = re.compile(r"[a-zA-Z_$][a-zA-Z0-9_.$-]*")
# Retain padding accepted by either port's previous whitespace pattern.
_PADDING = re.compile(
    r"[\x09-\x0d\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+"
)
_EVENT = re.compile(r"[\"'/{}\[\],:]")
_SPACE = _PADDING.pattern[:-1]
_KEY = re.compile("(" + _NAME.pattern + ")" + _SPACE + "*:")
_POSSIBLE_KEY = re.compile(r"[{,]" + _SPACE + "*" + _NAME.pattern + _SPACE + "*:")


def _trivia_end(text: str, start: int) -> tuple[int, bool]:
    index = start
    comments = False
    while True:
        if match := _PADDING.match(text, index):
            index = match.end()
        if index + 1 < len(text) and text[index] == "/" and text[index + 1] in "/*":
            comments = True
            index = comment_end(text, index)
        else:
            return index, comments


def apply(text: str) -> str:
    if ":" not in text:
        return text
    if "//" not in text and "/*" not in text and not _POSSIBLE_KEY.search(text):
        return text
    pieces: list[str] = []
    # True/False mark an object's key/other position; None marks an array.
    stack: list[bool | None] = []
    copied = index = 0
    while index < len(text):
        char = text[index]
        if char in "\"'":
            index = quoted_end(text, index)
            if stack and stack[-1] is not None:
                stack[-1] = False
            continue
        if char == "/" and index + 1 < len(text) and text[index + 1] in "/*":
            index = comment_end(text, index)
            continue
        if char in "{[":
            if stack and stack[-1] is not None:
                stack[-1] = False
            stack.append(True if char == "{" else None)
        elif char in "}]":
            if stack and char == ("]" if stack[-1] is None else "}"):
                stack.pop()
        elif char == ",":
            if stack and stack[-1] is not None:
                stack[-1] = True
        elif char == ":":
            if stack and stack[-1] is not None:
                stack[-1] = False
        else:
            if stack and stack[-1] is True:
                if match := _KEY.match(text, index):
                    pieces.extend((text[copied:index], '"', match[1], '":'))
                    stack[-1] = False
                    copied = index = match.end()
                    continue
                if padding := _PADDING.match(text, index):
                    index = padding.end()
                    continue
                match = _NAME.match(text, index)
                stack[-1] = False
                if match:
                    end = match.end()
                    colon, comments = _trivia_end(text, end)
                    if colon < len(text) and text[colon] == ":":
                        pieces.extend((text[copied:index], '"', match[0], '"'))
                        pieces.append(text[end : colon + 1] if comments else ":")
                        copied = index = colon + 1
                    else:
                        index = end
                    continue
            event = _EVENT.search(text, index + 1)
            index = event.start() if event else len(text)
            continue
        index += 1
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
