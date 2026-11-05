"""Strategy registry for JSON repair strategies."""

from collections.abc import Callable, Sequence

from outputguard.strategies import (
    extract_json,
    fix_booleans,
    fix_closers,
    fix_commas,
    fix_ellipsis,
    fix_encoding,
    fix_inner_quotes,
    fix_keys,
    fix_newlines,
    fix_quotes,
    fix_truncated,
    fix_unicode,
    fix_values,
    remove_comments,
    strip_fences,
)

Strategy = Callable[[str], str]

ALL_STRATEGIES: list[tuple[str, Strategy]] = [
    (fix_encoding.NAME, fix_encoding.apply),
    (strip_fences.NAME, strip_fences.apply),
    (extract_json.NAME, extract_json.apply),
    (remove_comments.NAME, remove_comments.apply),
    (fix_commas.NAME, fix_commas.apply),
    (fix_quotes.NAME, fix_quotes.apply),
    (fix_keys.NAME, fix_keys.apply),
    (fix_values.NAME, fix_values.apply),
    (fix_booleans.NAME, fix_booleans.apply),
    (fix_truncated.NAME, fix_truncated.apply),
    (fix_ellipsis.NAME, fix_ellipsis.apply),
    (fix_unicode.NAME, fix_unicode.apply),
    (fix_inner_quotes.NAME, fix_inner_quotes.apply),
    (fix_closers.NAME, fix_closers.apply),
    (fix_newlines.NAME, fix_newlines.apply),
]

STRATEGY_DESCRIPTIONS: dict[str, str] = {
    strip_fences.NAME: strip_fences.DESCRIPTION,
    extract_json.NAME: extract_json.DESCRIPTION,
    remove_comments.NAME: remove_comments.DESCRIPTION,
    fix_commas.NAME: fix_commas.DESCRIPTION,
    fix_quotes.NAME: fix_quotes.DESCRIPTION,
    fix_keys.NAME: fix_keys.DESCRIPTION,
    fix_values.NAME: fix_values.DESCRIPTION,
    fix_booleans.NAME: fix_booleans.DESCRIPTION,
    fix_truncated.NAME: fix_truncated.DESCRIPTION,
    fix_ellipsis.NAME: fix_ellipsis.DESCRIPTION,
    fix_encoding.NAME: fix_encoding.DESCRIPTION,
    fix_unicode.NAME: fix_unicode.DESCRIPTION,
    fix_inner_quotes.NAME: fix_inner_quotes.DESCRIPTION,
    fix_closers.NAME: fix_closers.DESCRIPTION,
    fix_newlines.NAME: fix_newlines.DESCRIPTION,
}


def get_strategy(name: str) -> Strategy:
    if not isinstance(name, str):
        raise TypeError("strategy name must be a string")
    for n, fn in ALL_STRATEGIES:
        if n == name:
            return fn
    raise ValueError(f"Unknown strategy: {name!r}")


def select_strategy_names(names: Sequence[str] | None) -> list[str] | None:
    """Validate a selection and copy it so callers retain ownership of their input."""
    if names is None:
        return None
    if isinstance(names, (str, bytes, bytearray)) or not isinstance(names, Sequence):
        raise TypeError("strategies must be a sequence of strategy names")
    selected = list(names)
    known = {name for name, _ in ALL_STRATEGIES}
    for name in selected:
        if not isinstance(name, str):
            raise TypeError("strategy name must be a string")
        if name not in known:
            raise ValueError(f"Unknown strategy: {name!r}")
    return selected


def get_strategies(names: Sequence[str] | None = None) -> list[tuple[str, Strategy]]:
    selected = select_strategy_names(names)
    if selected is None:
        return list(ALL_STRATEGIES)
    requested = set(selected)
    return [(n, fn) for n, fn in ALL_STRATEGIES if n in requested]
