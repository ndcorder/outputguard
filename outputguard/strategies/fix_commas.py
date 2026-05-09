"""Remove trailing commas before closing braces/brackets."""

import re

NAME = "fix_commas"

_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def apply(text: str) -> str:
    return _TRAILING_COMMA_RE.sub(r"\1", text)
