import json
from pathlib import Path

import pytest

from benchmarks.comparison import assert_json_equal
from outputguard import OutputGuard, guarded_generate, validate, validate_and_repair, validate_batch
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import FormatParseError, parse_document

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/python_strings.json").read_text())
LOCATIONS = [
    pytest.param(case, location, id=f"{case['name']}-{location}")
    for case in CASES
    for location in (["root"] if case.get("root_only") else ["root", "property", "list"])
]
pytestmark = [
    pytest.mark.filterwarnings("ignore::SyntaxWarning"),
    pytest.mark.filterwarnings("ignore::DeprecationWarning"),
]


def document(case, location):
    text, value = case["text"], case.get("value")
    if location == "property":
        return "{'value': " + text + "}", {"value": value}
    if location == "list":
        return "[" + text + "]", [value]
    return text, value


@pytest.mark.parametrize(("case", "location"), LOCATIONS)
def test_python_string_values_and_parse_failure_categories(case, location):
    text, value = document(case, location)
    for schema in (True, False):
        result = validate(text, schema, format="python")
        assert result.original_text == text and not result.repaired
        assert not result.strategies_applied
        if not case["valid"]:
            assert not result.valid and result.parse_error and result.data is None
            assert [(error.path, error.schema_path) for error in result.errors] == [("$", "")]
        else:
            assert result.valid is schema and result.parse_error is None
            assert_json_equal(result.data, value, case["name"])
            assert [error.path for error in result.errors] == ([] if schema else ["$"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_python_string_parser_contract_and_repair_short_circuit(case):
    if not case["valid"]:
        with pytest.raises(FormatParseError):
            parse_document(case["text"], "python")
        return
    assert parse_document(case["text"], "python") == case["value"]
    result = validate_and_repair(case["text"], {"const": case["value"]}, format="python")
    assert result.valid and not result.repaired and result.parse_error is None
    assert result.data == case["value"] and result.repaired_text == ""


@pytest.mark.parametrize("format", ["python", "python-literal", "py", "literal"])
def test_aliases_decode_keys_and_preserve_raw_property_values(format):
    text = r"{'__' 'proto__': r'\q', u'normal': ('A' '\x42')}"
    result = validate(text, {"const": {"__proto__": "\\q", "normal": "AB"}}, format=format)
    assert result.valid and result.parse_error is None


def test_guard_and_batch_use_decoded_string_values():
    guard = OutputGuard(format="python", strategies=[])
    assert guard.parse(r"r'\q'", {"const": "\\q"}) == "\\q"
    with pytest.raises(ParseError):
        guard.parse("'a\nb'", True)
    with pytest.raises(SchemaValidationError):
        guard.parse(r"'\x41'", {"const": "B"})
    batch = validate_batch([r"'\x41'", r"r'\x41'", "'a\nb'"], {"const": "A"}, guard=guard)
    assert (batch.summary.valid, batch.summary.parse_failures, batch.summary.schema_failures) == (
        1,
        1,
        1,
    )


def test_generation_reports_schema_failures_after_string_decoding():
    def generate(prompt, context):
        if context.attempt == 0:
            return r"r'\x41'"
        assert context.previous_result.parse_error is None
        assert context.previous_result.data == "\\x41"
        return r"'\x41'"

    result = guarded_generate(
        generate=generate, prompt="Return a Python string", schema={"const": "A"}, format="python"
    )
    assert result.valid and result.data == "A" and len(result.attempts) == 2


def test_native_python_named_unicode_escapes_remain_available():
    assert parse_document(r"'\N{LATIN CAPITAL LETTER A}'", "python") == "A"
