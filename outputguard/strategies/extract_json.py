"""Extract the first balanced JSON object or array from surrounding text."""

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "extract_json"
DESCRIPTION = "Extract JSON object/array from surrounding text"


def apply(text: str) -> str:
    search_start = 0
    while search_start < len(text) and text[search_start] in " \t\r\n":
        search_start += 1
    if search_start < len(text) and text[search_start] in "\"'":
        cursor = quoted_end(text, search_start)
        while cursor < len(text) and text[cursor] in " \t\r\n":
            cursor += 1
        if cursor == len(text):
            return text
        search_start = cursor  # Ignore brackets inside a closed quoted introduction.
    # Find the first { or [
    start = -1
    i = search_start
    while i < len(text):
        ch = text[i]
        if ch in "{[":
            start = i
            break
        if ch == "/" and i + 1 < len(text) and text[i + 1] in "/*":
            i = comment_end(text, i)
        else:
            i += 1

    if start == -1:
        return text

    stack = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch in "\"'":
            i = quoted_end(text, i)
            continue
        if ch == "/" and i + 1 < len(text) and text[i + 1] in "/*":
            i = comment_end(text, i)
            continue
        if ch in "{[":
            stack += 1
        elif ch in "}]":
            stack -= 1
            if stack == 0:
                return text[start : i + 1]
        i += 1

    # No balanced close found — return from start to end
    return text[start:]
