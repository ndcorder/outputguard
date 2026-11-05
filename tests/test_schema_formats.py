import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker

from outputguard import OutputGuard, guarded_generate, validate, validate_and_repair, validate_batch
from outputguard.exceptions import SchemaValidationError

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/schema_formats.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("location", ["root", "property", "reference"])
def test_shared_format_assertions(case, location):
    schema = {"format": case["format"]}
    data, path = case["value"], "$"
    if location == "property":
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "properties": {"a/b": schema},
        }
        data, path = {"a/b": data}, '$["a/b"]'
    elif location == "reference":
        schema = {"default": schema, "$ref": "#/default"}
    before = copy.deepcopy(schema)
    result = validate(json.dumps(data), schema)
    assert result.valid is case["valid"]
    assert result.parse_error is None and not result.repaired
    assert result.data == data
    assert [(error.path, error.value) for error in result.errors] == (
        [] if case["valid"] else [(path, case["value"])]
    )
    if not case["valid"]:
        assert result.errors[0].schema_path.endswith(".format")
        assert case["format"] in result.errors[0].message
    assert schema == before


def test_format_failures_after_repairs_are_schema_errors():
    schema = {"properties": {"email": {"format": "email"}}}
    result = validate_and_repair('{"email":"bad",}', schema)
    assert not result.valid and result.repaired and result.parse_error is None
    assert result.data == {"email": "bad"}
    assert result.strategies_applied == ["fix_commas"]
    assert [(error.path, error.value) for error in result.errors] == [("$.email", "bad")]
    with pytest.raises(SchemaValidationError):
        OutputGuard().parse('{"email":"bad",}', schema)


@pytest.mark.parametrize("format", ["json", "yaml", "toml", "python", "auto"])
def test_format_assertions_apply_after_each_document_parser(format):
    text = 'email = "bad"' if format == "toml" else '{"email":"bad"}'
    result = validate(text, {"properties": {"email": {"format": "email"}}}, format=format)
    assert not result.valid and result.parse_error is None
    assert [(error.path, error.value) for error in result.errors] == [("$.email", "bad")]


def test_format_checker_follows_nested_resource_scopes_and_ignores_reference_siblings():
    schema = {
        "$id": "https://outputguard.test/formats/root.json",
        "definitions": {
            "child": {
                "$id": "child.json",
                "properties": {"email": {"format": "email"}},
            }
        },
        "$ref": "child.json",
        "format": "email",
    }
    assert validate('{"email":"ada@example.com"}', schema).valid
    result = validate('{"email":"bad"}', schema)
    assert [(error.path, error.value) for error in result.errors] == [("$.email", "bad")]


def test_format_failures_are_counted_and_used_in_generation_feedback():
    schema = {"format": "email"}
    batch = validate_batch(['"ada@example.com"', '"bad"', "{"], schema)
    assert batch.summary.valid == 1
    assert batch.summary.parse_failures == 1
    assert batch.summary.schema_failures == 1

    def generate(prompt, context):
        if context.attempt == 0:
            return '"bad"'
        assert context.previous_result.parse_error is None
        assert "email" in prompt
        return '"ada@example.com"'

    assert guarded_generate(prompt="Return an email", schema=schema, generate=generate).valid


def test_native_format_checkers_and_registrations_are_unchanged():
    before = dict(FormatChecker.checkers)
    native = FormatChecker()
    native.checks("email")(lambda value: True)
    assert native.conforms("bad", "email")
    assert not validate('"bad"', {"format": "email"}).valid
    assert Draft7Validator({"format": "email"}).is_valid("bad")
    assert FormatChecker.checkers == before
