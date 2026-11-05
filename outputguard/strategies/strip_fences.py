"""Strip markdown code fences wrapping structured output."""

import re

from outputguard.strategies._lexical import comment_end, quoted_end

NAME = "strip_fences"
DESCRIPTION = "Remove markdown code fences (```json ... ```)"

_SPACE = r"[\x09-\x0d\x1c-\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"
_PADDING = (
    "\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680"
    + "".join(chr(code) for code in range(0x2000, 0x200B))
    + "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_OPENING = r"```[a-zA-Z]*" + _SPACE + r"*\n"
_TOKEN = re.compile(_OPENING + r"|[\"'/{}\[\]]")
_FENCE_RE = re.compile(_OPENING + r"(.*?)\n" + _SPACE + "*```", re.DOTALL)


def apply(text: str) -> str:
    if "```" not in text:
        return text
    root = 0
    while root < len(text) and text[root] in _PADDING:
        root += 1
    stack: list[str] = []
    index = 0
    while token := _TOKEN.search(text, index):
        start = token.start()
        char = text[start]
        if char in "\"'" and (stack or start == root):
            index = quoted_end(text, start)
            continue
        if char == "/" and start + 1 < len(text) and text[start + 1] in "/*":
            index = comment_end(text, start)
            continue
        if char == "`" and not stack:
            closed = _FENCE_RE.match(text, start)
            body = closed[1] if closed else text[token.end() :]
            return body.strip(_PADDING)
        if char in "{[":
            stack.append(char)
        elif stack and char == ("}" if stack[-1] == "{" else "]"):
            stack.pop()
        index = token.end()
    return text
