"""Validate configuration before processing inputs or invoking generators."""

from outputguard.formats import normalize_format

MAX_SAFE_INTEGER = 2**53 - 1


def select_format(override: str | None, default: str = "json") -> str:
    selected = default if override is None else override
    normalize_format(selected)
    # Preserve the selected spelling in results, reports, and batch counts.
    return selected


def attempt_limit(value: int | float, name: str) -> int:
    # Integral floats represent the same JSON number as an integer in JS.
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= MAX_SAFE_INTEGER
        and int(value) == value
    ):
        return int(value)
    raise ValueError(f"{name} must be a nonnegative safe integer (0 to {MAX_SAFE_INTEGER})")


def generation_callbacks(generate: object, on_attempt: object) -> None:
    if not callable(generate):
        raise TypeError("generate must be callable")
    if on_attempt is not None and not callable(on_attempt):
        raise TypeError("on_attempt must be callable")
