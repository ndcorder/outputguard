import json
import math
from pathlib import Path

import pytest

from outputguard import OutputGuard, guarded_generate, validate, validate_and_repair, validate_batch
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import FormatParseError, parse_document

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/python_numbers.json").read_text())
LOCATIONS = [
    pytest.param(case, location, id=f"{case['name']}-{location}")
    for case in CASES
    for location in (["root"] if case.get("root_only") else ["root", "property", "list"])
]


def document(text, location):
    if location == "property":
        return "{'value': " + text + "}"
    if location == "list":
        return "[" + text + "]"
    return text


def assert_number(value, case):
    expected = case.get("value")
    if "value_kind" in case:
        expected = -math.inf if case["value_kind"] == "negative_infinity" else math.inf
    assert type(value) is (float if case["number_type"] == "float" else int)
    assert value == expected
    if value == 0:
        assert math.copysign(1, value) == math.copysign(1, expected)


@pytest.mark.parametrize(("case", "location"), LOCATIONS)
def test_python_number_values_and_parse_failure_categories(case, location):
    text = document(case["text"], location)
    for schema in (True, False):
        result = validate(text, schema, format="python")
        assert result.original_text == text and not result.repaired
        assert not result.strategies_applied
        if not case["valid"]:
            assert not result.valid and result.parse_error and result.data is None
            assert [(error.path, error.schema_path) for error in result.errors] == [("$", "")]
        else:
            assert result.valid is schema and result.parse_error is None
            value = result.data
            if location == "property":
                value = value["value"]
            elif location == "list":
                value = value[0]
            assert_number(value, case)
            assert [error.path for error in result.errors] == ([] if schema else ["$"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_number_parser_contract_and_repair_short_circuit(case):
    if not case["valid"]:
        with pytest.raises(FormatParseError):
            parse_document(case["text"], "python")
        return
    assert_number(parse_document(case["text"], "python"), case)
    schema = True if "value_kind" in case else {"const": case["value"]}
    result = validate_and_repair(case["text"], schema, format="python")
    assert result.valid and not result.repaired and result.parse_error is None
    assert result.repaired_text == "" and not result.strategies_applied
    assert_number(result.data, case)


@pytest.mark.parametrize("format", ["python", "python-literal", "py", "literal"])
def test_number_aliases_and_signed_nested_values(format):
    text = "{'x': - (0x_2A), 'y': .1_25e2}"
    result = validate(text, {"const": {"x": -42, "y": 12.5}}, format=format)
    assert result.valid and result.parse_error is None


def test_number_guards_and_batch_failure_counts():
    guard = OutputGuard(format="python", strategies=[])
    assert guard.parse("+ (0x_2A)", {"const": 42}) == 42
    with pytest.raises(ParseError):
        guard.parse("1__0", True)
    with pytest.raises(SchemaValidationError):
        guard.parse("0x2b", {"const": 42})
    result = validate_batch(["0x2a", "1__0", "1.e2"], {"maximum": 50}, guard=guard)
    assert (
        result.summary.valid,
        result.summary.parse_failures,
        result.summary.schema_failures,
    ) == (
        1,
        1,
        1,
    )


def test_generation_distinguishes_bad_number_syntax_from_wrong_value():
    def generate(prompt, context):
        if context.attempt == 0:
            return "1__0"
        if context.attempt == 1:
            assert context.previous_result.parse_error
            return "0x2b"
        assert context.previous_result.parse_error is None
        assert context.previous_result.data == 43
        return "+ (0x_2a)"

    result = guarded_generate(
        generate=generate, prompt="Return a Python number", schema={"const": 42}, format="python"
    )
    assert result.valid and result.data == 42 and len(result.attempts) == 3


def test_native_python_integer_precision_remains_available():
    assert parse_document("0x20000000000001", "python") == 9007199254740993


@pytest.mark.parametrize(
    ("zeros", "value"), [(30, 1e-31), (300, 1e-301), (3000, 0.0), (30000, 0.0)]
)
def test_long_fraction_tokens_and_invalid_trailing_underscores(zeros, value):
    text = "0." + "0_" * zeros + "1"
    result = validate(text, {"const": value}, format="python")
    assert result.valid and result.parse_error is None
    assert type(result.data) is float and result.data == value
    invalid = validate(text + "_", True, format="python")
    assert not invalid.valid and invalid.parse_error and invalid.data is None
