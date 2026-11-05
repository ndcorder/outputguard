"""Replace bare Python booleans and None without changing JSON strings."""

from outputguard.strategies._bare_values import make_replacer

NAME = "fix_booleans"
DESCRIPTION = "Replace Python True/False/None with true/false/null"

apply = make_replacer({"True": "true", "False": "false", "None": "null"})
