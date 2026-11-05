"""Validate public input types without coercion or partial batch work."""

from collections.abc import Sequence
from typing import TypeGuard


def is_text(value: object) -> TypeGuard[str]:
    # Inspect the actual type; __class__ can be spoofed by non-string objects.
    return issubclass(type(value), str)


def require_text(value: object, name: str = "text") -> str:
    if not is_text(value):
        raise TypeError(f"{name} must be a string")
    return value


def require_schema(value: object) -> None:
    if not issubclass(type(value), (dict, bool)):
        raise TypeError("schema must be an object or boolean")


def text_sequence(texts: Sequence[str]) -> list[str]:
    actual_type = type(texts)
    if issubclass(actual_type, (str, bytes, bytearray, memoryview)) or not issubclass(
        actual_type, Sequence
    ):
        raise TypeError("texts must be a sequence of strings")
    selected = list(texts)
    for index, text in enumerate(selected):
        if not is_text(text):
            raise TypeError(f"texts[{index}] must be a string")
    return selected
