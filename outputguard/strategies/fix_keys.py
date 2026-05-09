"""Add double quotes to unquoted object keys."""

import re

NAME = "fix_keys"
DESCRIPTION = "Add double quotes to unquoted object keys"

# Match unquoted keys after { or , (with optional whitespace/newlines)
_UNQUOTED_KEY_RE = re.compile(
    r'([{,]\s*)([a-zA-Z_$][a-zA-Z0-9_.$-]*)\s*:'
)


def apply(text: str) -> str:
    # We need to avoid replacing inside strings.
    # Strategy: split text into string-literal and non-string segments,
    # only apply regex to non-string segments.
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        if text[i] == '"':
            # Consume the whole string literal
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            result.append(text[i:j])
            i = j
        else:
            # Find next string literal or end
            j = text.find('"', i)
            if j == -1:
                j = n
            segment = text[i:j]
            segment = _UNQUOTED_KEY_RE.sub(r'\1"\2":', segment)
            result.append(segment)
            i = j

    return "".join(result)
