"""Fix unescaped double quotes inside JSON string values."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_inner_quotes"
DESCRIPTION = "Escape unescaped double quotes inside string values"

_PADDING = re.compile(
    r"[\x09-\x0d\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+"
)
_NON_PADDING = re.compile("[^" + _PADDING.pattern[1:-2] + "]")
_EVENT = re.compile(r"[\"'/{}\[\],:]")


def _trivia_end(text: str, start: int) -> int:
    index = start
    while True:
        if match := _PADDING.match(text, index):
            index = match.end()
        if index + 1 < len(text) and text[index] == "/" and text[index + 1] in "/*":
            index = comment_end(text, index)
        else:
            return index


def apply(text: str) -> str:
    if '"' not in text:
        return text
    pieces: list[str] = []
    stack: list[str] = []
    previous = ""
    copied = index = 0
    while event := _EVENT.search(text, index):
        start = event.start()
        if _NON_PADDING.search(text, index, start):
            previous = "token"
        char = text[start]
        if char == "/" and start + 1 < len(text) and text[start + 1] in "/*":
            index = comment_end(text, start)
            continue
        if char in "\"'":
            container = stack[-1] if stack else ""
            is_value = (
                not stack
                and not previous
                or container == "{"
                and previous == ":"
                or container == "["
                and previous in ("[", ",")
            )
            end = quoted_end(text, start)
            if char == '"' and is_value:
                while end < len(text):
                    following = _trivia_end(text, end)
                    if following == len(text) or text[following] in ",}]:":
                        break
                    pieces.extend((text[copied : end - 1], '\\"'))
                    copied = end
                    end = quoted_end(text, end - 1)
            index = end
            previous = "string"
            continue
        if char in "{[":
            stack.append(char)
        elif char in "}]" and stack and stack[-1] == ("{" if char == "}" else "["):
            stack.pop()
        previous = char
        index = start + 1
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
