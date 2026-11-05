"""Balance missing closing braces/brackets without changing quoted literals."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "fix_closers"
DESCRIPTION = "Balance missing closing braces and brackets"

_MATCH = {"{": "}", "[": "]"}
_EVENT = re.compile(r"[\"'/{}\[\]]")
_NON_PADDING = re.compile(
    r"[^\x09-\x0d\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
)


def apply(text: str) -> str:
    if "{" not in text and "[" not in text:
        return text
    stack: list[str] = []
    pieces: list[str] = []
    copied = index = 0
    trailing_comment: int | None = None
    while event := _EVENT.search(text, index):
        start = event.start()
        if trailing_comment is not None and _NON_PADDING.search(text, index, start):
            trailing_comment = None
        char = text[start]
        if char == "/" and start + 1 < len(text) and text[start + 1] in "/*":
            if trailing_comment is None:
                trailing_comment = start
            index = comment_end(text, start)
            continue
        trailing_comment = None
        if char in "\"'":
            index = quoted_end(text, start)
            if index == len(text):
                # A brace appended inside an unfinished string changes its data.
                close = index - 1
                if close <= start or text[close] != char:
                    return text
                back = close
                while back > start and text[back - 1] == "\\":
                    back -= 1
                if (close - back) % 2:
                    return text
            continue
        if char in _MATCH:
            stack.append(_MATCH[char])
        elif char in "}]":
            if not stack:
                return text
            if stack[-1] != char:
                if char not in stack:
                    return text  # An unmatched closer gives no missing-opener evidence.
                missing = []
                while stack[-1] != char:
                    missing.append(stack.pop())
                pieces.extend((text[copied:start], "".join(missing)))
                copied = start
            stack.pop()
        index = start + 1
    if trailing_comment is not None and _NON_PADDING.search(text, index):
        trailing_comment = None
    if stack:
        # Keep added delimiters outside a final line or unfinished block comment.
        end = len(text) if trailing_comment is None else trailing_comment
        pieces.extend((text[copied:end], "".join(reversed(stack))))
        copied = end
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
