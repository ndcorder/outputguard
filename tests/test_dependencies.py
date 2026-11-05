import json

import pytest

import outputguard


@pytest.mark.parametrize("trigger", ["__proto__", "constructor", "toString", "flag"])
def test_property_dependencies_apply_to_own_property_presence(trigger):
    schema = {"dependencies": {trigger: ["a", "b"]}}
    data = {trigger: False}
    result = outputguard.validate(json.dumps(data), schema)
    assert not result.valid
    assert len(result.errors) == 2
    assert all(
        error.path == "$" and error.schema_path == "$.dependencies" for error in result.errors
    )
    assert all(error.value == data for error in result.errors)
    assert outputguard.validate(json.dumps({**data, "a": None, "b": 0}), schema).valid
    assert outputguard.validate("{}", schema).valid


@pytest.mark.parametrize(
    "dependency", [False, {"required": ["a"]}, {"properties": {"value": {"type": "integer"}}}]
)
def test_schema_dependencies_apply_to_the_whole_object(dependency):
    result = outputguard.validate(
        '{"__proto__":null,"value":"wrong"}', {"dependencies": {"__proto__": dependency}}
    )
    assert not result.valid
    assert len(result.errors) == 1
    assert ".dependencies.__proto__" in result.errors[0].schema_path


@pytest.mark.parametrize("data", [None, True, 42, "text", []])
def test_dependencies_do_not_apply_to_non_objects(data):
    assert outputguard.validate(json.dumps(data), {"dependencies": {"__proto__": False}}).valid


@pytest.mark.parametrize("dependency", [[], True, {}])
def test_noop_dependencies_accept_values(dependency):
    assert outputguard.validate(
        '{"__proto__":null}', {"dependencies": {"__proto__": dependency}}
    ).valid


def test_dependencies_combine_with_other_constraints_without_mutation():
    schema = {
        "dependencies": {"__proto__": ["a"]},
        "allOf": [{"required": ["b"]}],
        "if": {"required": ["flag"]},
        "then": {"required": ["c"]},
    }
    before = json.dumps(schema)
    assert outputguard.validate('{"__proto__":null,"a":0,"b":0,"flag":true,"c":0}', schema).valid
    assert not outputguard.validate('{"__proto__":null,"b":0}', schema).valid
    assert not outputguard.validate('{"a":0,"flag":true,"c":0}', schema).valid
    assert json.dumps(schema) == before


def test_dependencies_preserve_local_references():
    schema = {
        "definitions": {"needsA": {"required": ["a"]}},
        "dependencies": {"__proto__": {"$ref": "#/definitions/needsA"}},
    }
    assert not outputguard.validate('{"__proto__":null}', schema).valid
    assert outputguard.validate('{"__proto__":null,"a":1}', schema).valid


def test_dependency_failures_keep_repair_details():
    result = outputguard.validate_and_repair(
        '```json\n{"__proto__":null}\n```', {"dependencies": {"__proto__": ["a"]}}
    )
    assert not result.valid
    assert result.repaired
    assert result.parse_error is None
    assert len(result.errors) == 1


def test_generation_uses_dependency_feedback():
    def generate(prompt, context):
        if context.attempt:
            assert "__proto__" in prompt
            assert "a" in prompt
        return '{"__proto__":null,"a":1}' if context.attempt else '{"__proto__":null}'

    result = outputguard.guarded_generate(
        prompt="Return JSON", schema={"dependencies": {"__proto__": ["a"]}}, generate=generate
    )
    assert result.valid
    assert len(result.attempts) == 2


@pytest.mark.parametrize("keyword", ["properties", "dependencies"])
def test_draft7_reference_siblings_are_ignored(keyword):
    schema = {
        "definitions": {"base": True},
        "$ref": "#/definitions/base",
        keyword: {"flag": False, "__proto__": False},
    }
    assert outputguard.validate('{"flag":true,"__proto__":true}', schema).valid


def test_references_keep_sibling_locations_available():
    schema = {
        "$ref": "#/properties/value",
        "properties": {"value": {"type": "integer"}},
        "type": "string",
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_retry_prompt_does_not_describe_ignored_reference_siblings():
    schema = {
        "$ref": "#/definitions/base",
        "definitions": {"base": {"type": "integer"}},
        "type": "object",
        "properties": {"siblingOnly": False},
    }
    result = outputguard.validate('"wrong"', schema)
    prompt = outputguard.retry_prompt('"wrong"', schema, result.errors)
    assert "integer" in prompt
    assert "siblingOnly" not in prompt


def test_nested_references_are_labeled_without_ignored_type_hints():
    schema = {
        "definitions": {"base": {"type": "integer"}},
        "properties": {"value": {"$ref": "#/definitions/base", "type": "string"}},
    }
    prompt = outputguard.retry_prompt("{}", schema, [])
    assert "value (referenced schema)" in prompt
    assert "string" not in prompt
