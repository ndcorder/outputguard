"""Replace ... placeholders with valid JSON values."""

import re

NAME = "fix_ellipsis"
DESCRIPTION = "Replace ... placeholders with valid JSON values"


def apply(text: str) -> str:
    try:
        result: list[str] = []
        i = 0
        n = len(text)
        in_string = False

        while i < n:
            ch = text[i]

            # Handle string state
            if in_string:
                result.append(ch)
                if ch == "\\" and i + 1 < n:
                    result.append(text[i + 1])
                    i += 2
                    continue
                if ch == '"':
                    in_string = False
                i += 1
                continue

            if ch == '"':
                in_string = True
                result.append(ch)
                i += 1
                continue

            # Check for // single-line comments containing ...
            if ch == "/" and i + 1 < n and text[i + 1] == "/":
                # Skip the entire comment to end of line
                while i < n and text[i] != "\n":
                    i += 1
                continue

            # Check for /* multi-line comments containing ... */
            if ch == "/" and i + 1 < n and text[i + 1] == "*":
                i += 2
                while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2  # skip */
                continue

            # Outside a string — check for ...
            if ch == "." and i + 2 < n and text[i + 1] == "." and text[i + 2] == ".":
                # Look at the character before the dots (skip whitespace)
                before = "".join(result).rstrip()
                # Look at the character after the dots
                after_idx = i + 3
                while after_idx < n and text[after_idx] in " \t\r\n":
                    after_idx += 1
                after_ch = text[after_idx] if after_idx < n else ""

                if before.endswith("[") and after_ch == "]":
                    # [...] -> [] — skip the dots
                    i += 3
                    continue
                elif before.endswith("{") and after_ch == "}":
                    # {...} -> {} — skip the dots
                    i += 3
                    continue
                elif before.endswith(",") and after_ch in "],":
                    # ... as a trailing array element after comma —
                    # remove the dots AND the preceding comma
                    joined = "".join(result)
                    stripped = joined.rstrip()
                    if stripped.endswith(","):
                        result.clear()
                        result.append(stripped[:-1])
                    i += 3
                    continue
                else:
                    # Standalone ... as a value -> null
                    result.append("null")
                    i += 3
                    continue

            result.append(ch)
            i += 1

        output = "".join(result)

        # Clean up trailing commas that may result from removing
        # ellipsis elements (e.g. [1, 2, ...] -> [1, 2, null] is fine,
        # but if the ... was already the trailing element we may have
        # a dangling comma before a closer).
        output = re.sub(r",\s*([\]\}])", r"\1", output)

        # Also handle "...", as array element — the quotes were kept
        # because it was inside a string; remove "..." elements.
        # We need to be careful: only remove "..." that is an array
        # element (preceded by , or [).
        output = re.sub(r',\s*"\.\.\.(more[^"]*)?"', "", output)
        output = re.sub(r'"\.\.\.(more[^"]*)?"\s*,\s*', "", output)

        return output
    except Exception:
        return text
