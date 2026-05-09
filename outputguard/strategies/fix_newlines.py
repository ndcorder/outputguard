"""Escape unescaped newlines, carriage returns, and tabs inside JSON string values."""

NAME = "fix_newlines"
DESCRIPTION = "Escape unescaped newlines/tabs inside string values"


def apply(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        ch = text[i]

        if not in_string:
            if ch == '"':
                in_string = True
            result.append(ch)
            i += 1
            continue

        # Inside a string
        if ch == "\\":
            # Already-escaped sequence — pass through as-is
            result.append(ch)
            if i + 1 < n:
                result.append(text[i + 1])
                i += 2
            else:
                i += 1
            continue

        if ch == '"':
            in_string = False
            result.append(ch)
            i += 1
            continue

        if ch == "\n":
            result.append("\\n")
            i += 1
            continue

        if ch == "\r":
            result.append("\\r")
            i += 1
            continue

        if ch == "\t":
            result.append("\\t")
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)
