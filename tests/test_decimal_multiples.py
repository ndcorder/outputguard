import json
from decimal import localcontext
from pathlib import Path

import jsonschema
import pytest

from outputguard import guarded_generate, validate, validate_and_repair, validate_batch

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/numeric_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("position", ["root", "property", "items", "resource", "literal"])
@pytest.mark.parametrize("explicit_dialect", [False, True])
def test_decimal_multiple_validity_and_source_diagnostics(case, position, explicit_dialect):
    constraint = {"type": "number", "multipleOf": case["divisor"]}
    if explicit_dialect:
        constraint["$schema"] = "http://json-schema.org/draft-07/schema#"
    value, path = json.loads(case["text"]), "$"
    if position == "property":
        schema, value, path = {"properties": {"a/b~c": constraint}}, {"a/b~c": value}, '$["a/b~c"]'
    elif position == "items":
        schema, value, path = {"items": constraint}, [value], "$[0]"
    elif position == "resource":
        schema = {
            "definitions": {"value": {"$id": "number.json", **constraint}},
            "$ref": "number.json",
        }
    elif position == "literal":
        schema = {"default": constraint, "$ref": "#%2Fdefault"}
    else:
        schema = constraint
    before = json.dumps(schema)
    for _ in range(2):
        result = validate(json.dumps(value), schema)
        assert result.valid is case["valid"]
        if not result.valid:
            expected_value = (
                value["a/b~c"]
                if position == "property"
                else value[0]
                if position == "items"
                else value
            )
            assert [(error.path, error.value) for error in result.errors] == [
                (path, expected_value)
            ]
            assert result.errors[0].schema_path.endswith(".multipleOf")
            assert "not a multiple" in result.errors[0].message
    assert json.dumps(schema) == before


@pytest.mark.parametrize("value", [None, False, True, "0.3", [], {}])
@pytest.mark.parametrize("typed", [False, True])
def test_multiple_of_only_applies_to_numbers(value, typed):
    schema = {"multipleOf": 0.1, **({"type": "number"} if typed else {})}
    result = validate(json.dumps(value), schema)
    assert result.valid is not typed
    if typed:
        assert all(error.schema_path.endswith(".type") for error in result.errors)


def test_decimal_context_precision_does_not_change_results():
    with localcontext() as context:
        context.prec = 1
        assert validate("2.01", {"multipleOf": 0.01}).valid
        assert not validate("2.011", {"multipleOf": 0.01}).valid
        assert validate("1e308", {"multipleOf": 1e-308}).valid


def test_decimal_step_changes_are_observed_without_retaining_schema_state():
    schema = {"multipleOf": 0.1}
    assert validate("0.3", schema).valid
    schema["multipleOf"] = 0.2
    assert not validate("0.3", schema).valid


def test_decimal_validation_leaves_native_keywords_and_registration_unchanged():
    keyword = jsonschema.Draft7Validator.VALIDATORS["multipleOf"]
    assert validate("0.3", {"multipleOf": 0.1}).valid
    assert jsonschema.Draft7Validator.VALIDATORS["multipleOf"] is keyword
    assert (
        jsonschema.validators.validator_for({"$schema": "http://json-schema.org/draft-07/schema#"})
        is jsonschema.Draft7Validator
    )


def test_decimal_multiples_flow_through_repairs_batches_and_generation():
    schema = {"properties": {"price": {"multipleOf": 0.01}}}
    good = '```json\n{"price":2.01}\n```'
    bad = '```json\n{"price":2.011}\n```'
    assert validate_and_repair(good, schema).valid
    failed = validate_and_repair(bad, schema)
    assert failed.repaired and not failed.valid
    assert [(error.path, error.value) for error in failed.errors] == [("$.price", 2.011)]
    batch = validate_batch([good, bad], schema, repair=True)
    assert (batch.summary.valid, batch.summary.schema_failures) == (1, 1)

    def generate(prompt, context):
        if context.attempt == 0:
            return bad
        assert "$.price" in prompt and "multiple" in prompt
        assert context.previous_result.data == {"price": 2.011}
        return good

    result = guarded_generate(prompt="Return a price", schema=schema, generate=generate)
    assert result.valid and result.data == {"price": 2.01}
    assert len(result.attempts) == 2


@pytest.mark.parametrize("format", ["json", "yaml", "toml", "python"])
@pytest.mark.parametrize(("value", "valid"), [("2.01", True), ("2.011", False)])
def test_decimal_checks_use_the_selected_document_format(format, value, valid):
    text = {
        "json": '{"price":' + value + "}",
        "yaml": "price: " + value,
        "toml": "price = " + value,
        "python": "{'price':" + value + "}",
    }[format]
    result = validate(text, {"properties": {"price": {"multipleOf": 0.01}}}, format=format)
    assert result.valid is valid
    assert result.data == {"price": float(value)}


def test_decimal_assertions_do_not_change_literal_numbers():
    literal = {"multipleOf": 0.1, "value": 0.3}
    schema = {
        "default": literal,
        "properties": {"amount": {"$ref": "#/default"}, "literal": {"const": literal}},
    }
    before = json.dumps(schema)
    assert validate(json.dumps({"amount": 0.3, "literal": literal}), schema).valid
    failed = validate(
        json.dumps({"amount": 0.3, "literal": {**literal, "value": 0.30000000000000004}}), schema
    )
    assert [error.path for error in failed.errors] == ["$.literal"]
    assert json.dumps(schema) == before
