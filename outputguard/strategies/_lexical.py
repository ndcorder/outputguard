"""Locate quoted spans and comments without decoding their contents."""

import re

_LINE_END = re.compile(r"[\r\n\u2028\u2029]")


def quoted_end(text: str, start: int) -> int:
    """Return the end of a quoted span, or EOF for an unfinished string."""
    quote = text[start]
    end = start
    while True:
        end = text.find(quote, end + 1)
        if end == -1:
            return len(text)
        back = end
        while back > start and text[back - 1] == "\\":
            back -= 1
        if (end - back) % 2 == 0:
            return end + 1


def comment_end(text: str, start: int) -> int:
    """Return the first line terminator or the position after a block comment."""
    if text[start + 1] == "/":
        match = _LINE_END.search(text, start + 2)
        return match.start() if match else len(text)
    end = text.find("*/", start + 2)
    return len(text) if end == -1 else end + 2
