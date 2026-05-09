"""Extract the first balanced JSON object or array from surrounding text."""

NAME = "extract_json"
DESCRIPTION = "Extract JSON object/array from surrounding text"


def apply(text: str) -> str:
    # Find the first { or [
    start = -1
    opener = ""
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            opener = ch
            break

    if start == -1:
        return text

    closer = "}" if opener == "{" else "]"
    stack = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == "\\" and in_string:
            escape = True
            continue

        if ch == '"' and not escape:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in "{[":
            stack += 1
        elif ch in "}]":
            stack -= 1
            if stack == 0:
                return text[start : i + 1]

    # No balanced close found — return from start to end
    return text[start:]
