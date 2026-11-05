"""Repair standalone ellipsis placeholders while preserving quoted text."""

import re

from outputguard.strategies._lexical import quoted_end
from outputguard.strategies.fix_commas import apply as fix_commas
from outputguard.strategies.remove_comments import apply as remove_comments

NAME = "fix_ellipsis"
DESCRIPTION = "Replace ... placeholders with valid JSON values"

_WHITESPACE = " \t\r\n"
_START = _WHITESPACE + "[:,{"
_END = _WHITESPACE + ",]}"
_SPECIAL = "\"'[]{}:,."
_NEXT_SPECIAL = re.compile(r"[\"'\[\]{}:,.]")


def apply(text: str) -> str:
    working = remove_comments(text)
    if "..." not in working:
        return fix_commas(working)
    result: list[str] = []
    stack: list[str] = []
    index = 0
    last = ""
    last_index = 0
    while index < len(working):
        char = working[index]
        if char in "\"'":
            end = quoted_end(working, index)
            result.append(working[index:end])
            last, last_index = char, len(result) - 1
            index = end
            continue
        if char not in _SPECIAL:
            match = _NEXT_SPECIAL.search(working, index + 1)
            end = match.start() if match else len(working)
            chunk = working[index:end]
            result.append(chunk)
            significant = chunk.rstrip(_WHITESPACE)
            if significant:
                last, last_index = significant[-1], len(result) - 1
            index = end
            continue
        if (
            char == "."
            and working.startswith("...", index)
            and (index == 0 or working[index - 1] in _START)
            and (index + 3 == len(working) or working[index + 3] in _END)
        ):
            end = index + 3
            while end < len(working) and working[end] in _WHITESPACE:
                end += 1
            after = working[end] if end < len(working) else ""
            container = stack[-1] if stack else ""
            if (container == "{" and last == ":") or (not stack and not last and not after):
                result.append("null")
                last, last_index = "l", len(result) - 1
                index += 3
                continue
            if (
                container
                and last in (container, ",")
                and after in (",", "}" if container == "{" else "]", "")
            ):
                if after == ",":
                    index = end + 1
                else:
                    if last == ",":
                        del result[last_index:]
                        last = ""
                    index += 3
                continue
        result.append(char)
        if char not in _WHITESPACE:
            last, last_index = char, len(result) - 1
            if char in "[{":
                stack.append(char)
            elif stack and char == ("}" if stack[-1] == "{" else "]"):
                stack.pop()
        index += 1
    return fix_commas("".join(result))
