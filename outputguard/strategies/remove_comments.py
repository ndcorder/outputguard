"""Strip JS-style comments from JSON-like text, preserving strings."""

NAME = "remove_comments"
DESCRIPTION = "Strip JS-style // and /* */ comments"


def apply(text: str) -> str:
    result: list[str] = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        ch = text[i]

        # Inside a JSON string — pass through, handling escapes
        if in_string:
            result.append(ch)
            if ch == "\\":
                # Emit the escaped character too
                if i + 1 < n:
                    result.append(text[i + 1])
                    i += 2
                    continue
            elif ch == '"':
                in_string = False
            i += 1
            continue

        # Outside a string
        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        # Check for // single-line comment
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            # Skip to end of line
            while i < n and text[i] != "\n":
                i += 1
            continue

        # Check for /* multi-line comment */
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2  # skip */
            continue

        result.append(ch)
        i += 1

    return "".join(result)
