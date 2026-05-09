"""Fix unescaped double quotes inside JSON string values."""

import re

NAME = "fix_inner_quotes"
DESCRIPTION = "Escape unescaped double quotes inside string values"

_KEY_VALUE_RE = re.compile(
    r'("[^"]*"\s*:\s*)"'  # match "key": " opening
)


def apply(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch != '"':
            result.append(ch)
            i += 1
            continue

        # We hit a ". Determine if this opens a string value.
        # Check if preceded by : (with optional whitespace) — that means it's a value string.
        prefix = "".join(result).rstrip()
        is_value = prefix.endswith(":")

        # Consume the opening quote
        result.append('"')
        i += 1

        if not is_value:
            # It's a key string or other — consume normally until closing quote
            while i < n:
                c = text[i]
                if c == "\\":
                    result.append(c)
                    if i + 1 < n:
                        result.append(text[i + 1])
                        i += 2
                    else:
                        i += 1
                    continue
                if c == '"':
                    result.append(c)
                    i += 1
                    break
                result.append(c)
                i += 1
            continue

        # It's a value string — find where it really ends.
        # The real closing quote is followed by , or } or ] or end-of-object whitespace.
        # Any " NOT followed by one of those delimiters is an inner quote to escape.
        len(result)
        while i < n:
            c = text[i]
            if c == "\\":
                result.append(c)
                if i + 1 < n:
                    result.append(text[i + 1])
                    i += 2
                else:
                    i += 1
                continue
            if c == '"':
                # Look ahead: is this the real closing quote?
                j = i + 1
                while j < n and text[j] in " \t\r\n":
                    j += 1
                if j >= n or text[j] in ",}]:":
                    # Real closing quote
                    result.append('"')
                    i += 1
                    break
                else:
                    # Inner quote — escape it
                    result.append('\\"')
                    i += 1
                    continue
            result.append(c)
            i += 1

    return "".join(result)
