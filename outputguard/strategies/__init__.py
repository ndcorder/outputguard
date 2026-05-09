"""Strategy registry for JSON repair strategies."""

from collections.abc import Callable

from outputguard.strategies import (
    extract_json,
    fix_booleans,
    fix_closers,
    fix_commas,
    fix_ellipsis,
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
    fix_unicode.NAME: fix_unicode.DESCRIPTION,
    fix_inner_quotes.NAME: fix_inner_quotes.DESCRIPTION,
    fix_closers.NAME: fix_closers.DESCRIPTION,
    fix_newlines.NAME: fix_newlines.DESCRIPTION,
}


def get_strategy(name: str) -> Strategy:
    for n, fn in ALL_STRATEGIES:
        if n == name:
            return fn
    raise ValueError(f"Unknown strategy: {name}")


def get_strategies(names: list[str] | None = None) -> list[tuple[str, Strategy]]:
    if names is None:
        return list(ALL_STRATEGIES)
    return [(n, fn) for n, fn in ALL_STRATEGIES if n in names]
