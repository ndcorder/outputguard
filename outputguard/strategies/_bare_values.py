"""Build linear scanners for bare values outside JSON strings."""

from collections.abc import Callable

_START = frozenset(" \t\r\n[:,")
_END = frozenset(" \t\r\n,]}")


def make_replacer(replacements: dict[str, str]) -> Callable[[str], str]:
    candidates: dict[str, list[tuple[str, str]]] = {}
    for token, replacement in replacements.items():
        candidates.setdefault(token[0], []).append((token, replacement))
    needles = tuple(dict.fromkeys(token.lstrip("+-") for token in replacements))

    def apply(text: str) -> str:
        if not any(token in text for token in needles):
            return text
        pieces: list[str] = []
        index = copied = 0
        in_string = False
        while index < len(text):
            char = text[index]
            if in_string:
                if char == "\\":
                    index += 2
                    continue
                if char == '"':
                    in_string = False
                index += 1
                continue
            if char == '"':
                in_string = True
                index += 1
                continue
            if index and text[index - 1] not in _START:
                index += 1
                continue
            for token, replacement in candidates.get(char, ()):
                end = index + len(token)
                if text.startswith(token, index) and (end == len(text) or text[end] in _END):
                    pieces.extend((text[copied:index], replacement))
                    copied = index = end
                    break
            else:
                index += 1
        if not pieces:
            return text
        pieces.append(text[copied:])
        return "".join(pieces)

    return apply
