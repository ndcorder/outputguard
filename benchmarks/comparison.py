"""Compare JSON results without Python's boolean/number equality coercion."""

from __future__ import annotations

import json
import math


def _kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) or isinstance(value, float) and math.isfinite(value):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unsupported"


def json_difference(expected, actual, path: str = "$") -> str | None:
    """Return the first difference, using JSON types and numerical equality."""
    expected_kind, actual_kind = _kind(expected), _kind(actual)
    if expected_kind == "unsupported" or actual_kind == "unsupported":
        return (
            f"{path}: unsupported JSON value ({type(expected).__name__}, {type(actual).__name__})"
        )
    if expected_kind != actual_kind:
        return f"{path}: expected {expected_kind}, got {actual_kind}"
    if expected_kind == "object":
        for side, value in (("expected", expected), ("actual", actual)):
            if any(not isinstance(key, str) for key in value):
                return f"{path}: {side} object has a non-string key"
        for key, value in expected.items():
            child_path = f"{path}[{json.dumps(key, ensure_ascii=False)}]"
            if key not in actual:
                return f"{child_path}: missing property"
            difference = json_difference(value, actual[key], child_path)
            if difference is not None:
                return difference
        for key in actual:
            if key not in expected:
                return f"{path}[{json.dumps(key, ensure_ascii=False)}]: unexpected property"
    elif expected_kind == "array":
        if len(expected) != len(actual):
            return f"{path}: expected array length {len(expected)}, got {len(actual)}"
        for index, (left, right) in enumerate(zip(expected, actual, strict=True)):
            difference = json_difference(left, right, f"{path}[{index}]")
            if difference is not None:
                return difference
    elif expected != actual:
        return (
            f"{path}: expected {json.dumps(expected, ensure_ascii=False)}, "
            f"got {json.dumps(actual, ensure_ascii=False)}"
        )
    return None


def same_json(left, right) -> bool:
    return json_difference(left, right) is None


def assert_json_equal(actual, expected, context: str = "JSON results differ") -> None:
    difference = json_difference(expected, actual)
    if difference is not None:
        raise ValueError(f"{context}: {difference}")
