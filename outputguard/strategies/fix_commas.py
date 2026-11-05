"""Remove trailing commas before closing braces/brackets."""

import re

NAME = "fix_commas"
DESCRIPTION = "Remove trailing commas before } and ]"

# Preserve the whitespace repairs accepted by either runtime's old \s pattern.
_PADDING = r"[\x09-\x0d\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
_TRAILING_COMMA_RE = re.compile("," + _PADDING + r"*[}\]]")
# Match each quoted span as one token, including an unfinished string or a final
# backslash. The quote alternatives always reach a closing quote or end of input.
_TOKENS = re.compile(
    r'"[^"\\]*(?:\\[\s\S][^"\\]*)*(?:"|\\?$)'
    r"|'[^'\\]*(?:\\[\s\S][^'\\]*)*(?:'|\\?$)|," + _PADDING + r"*[}\]]"
)


def apply(text: str) -> str:
    if "," not in text:
        return text
    if '"' not in text and "'" not in text:
        return _TRAILING_COMMA_RE.sub(lambda match: match[0][-1], text)
    if not _TRAILING_COMMA_RE.search(text):
        return text
    pieces: list[str] = []
    copied = 0
    for match in _TOKENS.finditer(text):
        index = match.start()
        if text[index] == ",":
            pieces.append(text[copied:index])
            copied = match.end() - 1  # Retain the closing brace/bracket.
    if not pieces:
        return text
    pieces.append(text[copied:])
    return "".join(pieces)
