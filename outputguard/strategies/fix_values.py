"""Replace bare nonstandard values without changing JSON strings."""

from outputguard.strategies._bare_values import make_replacer

NAME = "fix_values"
DESCRIPTION = "Replace NaN, Infinity, undefined with null"

apply = make_replacer(
    {
        token: "null"
        for token in ("NaN", "Infinity", "undefined", "-Infinity", "+Infinity", "-NaN", "+NaN")
    }
)
