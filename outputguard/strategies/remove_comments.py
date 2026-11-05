"""Strip JS-style comments from JSON-like text, preserving strings and tokens."""

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "remove_comments"
DESCRIPTION = "Strip JS-style // and /* */ comments"

_DELIMITERS = " \t\r\n{}[]:,\"'"


def apply(text: str) -> str:
    if "//" not in text and "/*" not in text:
        return text
    pieces: list[str] = []
    index = copied = 0
    last = ""
    while index < len(text):
        char = text[index]
        if char in "\"'":
            index = quoted_end(text, index)
            continue
        if char != "/" or index + 1 == len(text) or text[index + 1] not in "/*":
            index += 1
            continue
        prefix = text[copied:index]
        pieces.append(prefix)
        left = prefix[-1] if prefix else last
        end = comment_end(text, index)
        replacement = ""
        if text[index + 1] == "/":
            if end < len(text) and text[end] in "\u2028\u2029":
                replacement = "\n"
                end += 1
        elif end < len(text) and left and left not in _DELIMITERS and text[end] not in _DELIMITERS:
            # Removing a comment must not concatenate primitive tokens.
            replacement = " "
        if replacement:
            pieces.append(replacement)
        last = replacement[-1] if replacement else left
        copied = index = end
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
