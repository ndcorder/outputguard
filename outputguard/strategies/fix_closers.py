"""Balance missing closing braces/brackets."""

NAME = "fix_closers"
DESCRIPTION = "Balance missing closing braces and brackets"

_MATCH = {"{": "}", "[": "]"}


def apply(text: str) -> str:
    stack: list[str] = []
    in_string = False
    escape = False

    for ch in text:
        if escape:
            escape = False
            continue

        if ch == "\\" and in_string:
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]" and stack and stack[-1] == "[":
            stack.pop()

    if not stack:
        return text

    closers = "".join(_MATCH[opener] for opener in reversed(stack))
    return text + closers
