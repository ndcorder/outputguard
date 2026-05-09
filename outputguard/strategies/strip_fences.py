"""Strip markdown code fences wrapping JSON."""

import re

NAME = "strip_fences"
DESCRIPTION = "Remove markdown code fences (```json ... ```)"

_FENCE_RE = re.compile(
    r"```[a-zA-Z]*\s*\n(.*?)\n\s*```",
    re.DOTALL,
)


def apply(text: str) -> str:
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text
