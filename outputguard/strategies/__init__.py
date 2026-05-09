"""Strategy registry for JSON repair strategies."""

from outputguard.strategies import (
    extract_json,
    fix_closers,
    fix_commas,
    fix_keys,
    fix_newlines,
    fix_quotes,
    fix_values,
    remove_comments,
    strip_fences,
)

ALL_STRATEGIES: list[tuple[str, callable]] = [
    (strip_fences.NAME, strip_fences.apply),
    (extract_json.NAME, extract_json.apply),
    (remove_comments.NAME, remove_comments.apply),
    (fix_commas.NAME, fix_commas.apply),
    (fix_quotes.NAME, fix_quotes.apply),
    (fix_keys.NAME, fix_keys.apply),
    (fix_values.NAME, fix_values.apply),
    (fix_closers.NAME, fix_closers.apply),
    (fix_newlines.NAME, fix_newlines.apply),
]


def get_strategy(name: str) -> callable:
    for n, fn in ALL_STRATEGIES:
        if n == name:
            return fn
    raise ValueError(f"Unknown strategy: {name}")


def get_strategies(names: list[str] | None = None) -> list[tuple[str, callable]]:
    if names is None:
        return list(ALL_STRATEGIES)
    return [(n, fn) for n, fn in ALL_STRATEGIES if n in names]
