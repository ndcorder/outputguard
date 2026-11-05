"""Recover truncated JSON from token-limit cutoffs."""

from dataclasses import dataclass
from typing import Literal

from outputguard.strategies.fix_closers import apply as _fix_closers

NAME = "fix_truncated"
DESCRIPTION = "Recover truncated JSON from token-limit cutoffs"

_WHITESPACE = " \t\r\n"
_DELIMITERS = '{}[]:,"' + _WHITESPACE
_TRAILING = _WHITESPACE + ","


@dataclass(slots=True)
class _Object:
    phase: Literal["key", "colon", "value", "comma", "other"] = "key"
    entry_start: int = 0
    comma: int | None = None


def _start_value(frame: _Object) -> None:
    frame.phase = "comma" if frame.phase == "value" else "other"
    frame.comma = None


def apply(text: str) -> str:
    try:
        start = 0
        while start < len(text) and text[start] in _WHITESPACE:
            start += 1
        if start == len(text) or text[start] not in '{["':
            return text

        # Arrays need only a closing bracket; object members need key/value state.
        stack: list[_Object | None] = []
        in_string = escaped = False
        closers_checked = False
        key_owner: _Object | None = None
        i = start
        while i < len(text):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                    if key_owner is not None:
                        key_owner.phase = "colon"
                        key_owner = None
                i += 1
                continue

            if ch in _WHITESPACE:
                i += 1
                continue
            frame = stack[-1] if stack else None
            if ch == '"':
                in_string = True
                if frame is not None and frame.phase == "key":
                    frame.entry_start = frame.comma if frame.comma is not None else i
                    key_owner = frame
                elif frame is not None:
                    _start_value(frame)
            elif ch in "{[":
                if frame is not None:
                    _start_value(frame)
                stack.append(_Object() if ch == "{" else None)
            elif ch in "}]":
                if stack and ("}" if frame is not None else "]") == ch:
                    stack.pop()
                elif stack and not closers_checked:
                    closers_checked = True
                    balanced = _fix_closers(text)
                    if balanced != text:
                        return apply(balanced)
            elif ch == ":":
                if frame is not None:
                    frame.phase = "value" if frame.phase == "colon" else "other"
            elif ch == ",":
                if frame is not None and frame.phase == "comma":
                    frame.phase = "key"
                    frame.comma = i
            else:
                if frame is not None:
                    _start_value(frame)
                i += 1
                while i < len(text) and text[i] not in _DELIMITERS:
                    i += 1
                continue
            i += 1

        if not stack and not in_string:
            return text

        working = text
        end = len(text)
        if in_string:
            if key_owner is not None:
                end = key_owner.entry_start
            else:
                # Retain a final literal backslash without letting it escape
                # the closing quote. Other incomplete escapes remain for later strategies.
                working += ("\\" if escaped else "") + '"'
                end = len(working)
        elif (frame := stack[-1]) is not None and frame.phase == "colon":
            end = frame.entry_start

        # Only syntax whitespace is trimmed here. Whitespace inside an open
        # string was retained before its closing quote was added above.
        while end > start and working[end - 1] in _TRAILING:
            end -= 1
        suffix = ""
        frame = stack[-1] if stack else None
        if frame is not None and frame.phase == "value" and end > start and working[end - 1] == ":":
            suffix = " null"
        return (
            working[:end] + suffix + "".join("}" if f is not None else "]" for f in reversed(stack))
        )
    except Exception:
        return text
