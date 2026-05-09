"""Recover truncated JSON from token-limit cutoffs."""

import re

NAME = "fix_truncated"
DESCRIPTION = "Recover truncated JSON from token-limit cutoffs"

_MATCH = {"{": "}", "[": "]"}


def _count_unescaped_quotes(text: str) -> int:
    """Count unescaped double quotes in the full text."""
    count = 0
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            count += 1
        i += 1
    return count


def _balance_closers(text: str) -> str:
    """Append closing braces/brackets for any unmatched openers."""
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
        elif ch == "]":
            if stack and stack[-1] == "[":
                stack.pop()

    if not stack:
        return text

    closers = "".join(_MATCH[opener] for opener in reversed(stack))
    return text + closers


def apply(text: str) -> str:  # noqa: C901
    try:
        stripped = text.rstrip()
        if not stripped:
            return text

        # Only attempt repair on text that looks like JSON
        if stripped[0] not in "{[":
            return text

        # Step 1: Close an open string if we have an odd number of
        # unescaped quotes.
        working = stripped
        if _count_unescaped_quotes(working) % 2 != 0:
            working += '"'

        # Step 2: Clean up trailing structural problems.
        # Apply these in a loop because fixing one may reveal another.
        changed = True
        while changed:
            changed = False
            w = working.rstrip()

            # Trailing comma  ->  remove it
            if w.endswith(","):
                working = w[:-1]
                changed = True
                continue

            # Trailing colon (key with no value)  ->  add null
            if w.endswith(":"):
                working = w + " null"
                changed = True
                continue

            # A key-value where the value was never finished:
            # e.g. `"key": "` — the step-1 quote-close turned it into
            # `"key": ""` which is actually valid, so nothing extra needed.

        # Step 3: If truncation happened inside a partial key that was
        # never given a colon (e.g. `{"name": "Alice", "em"`), we now
        # have a dangling quoted key.  Remove it so the JSON can close.
        w = working.rstrip()
        # Pattern: trailing `"somekey"` that is preceded by a comma
        m = re.search(r',\s*"[^"]*"\s*$', w)
        if m:
            # Check if what follows the last comma is just a bare key
            # (no colon after it).  If so, strip it.
            after_comma = w[m.start() + 1 :].strip()
            if re.fullmatch(r'"[^"]*"', after_comma):
                # It's a lone key with no colon — remove it
                working = w[: m.start()]

        # Step 4: Balance closers
        working = _balance_closers(working)

        return working
    except Exception:
        return text
