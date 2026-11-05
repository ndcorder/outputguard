import json

import pytest

import outputguard

LITERAL_TARGETS = [
    ("const", "#/const"),
    ("enum", "#/enum/0"),
    ("default", "#/default"),
    ("examples", "#/examples/0"),
]
FALSE_CONSTRAINTS = [
    ({"properties": {"blocked": False}}, {"blocked": 1}, "$.blocked", "$.properties.blocked", 1),
    (
        {"properties": {"__proto__": False}},
        {"__proto__": 1},
        "$.__proto__",
        "$.properties.__proto__",
        1,
    ),
    (
        {"properties": {"a/b": False}},
        {"a/b": 1},
        '$["a/b"]',
        '$.properties["a/b"]',
        1,
    ),
    ({"items": False}, [1], "$[0]", "$.items", 1),
    ({"items": [True, False]}, [0, 1], "$[1]", "$.items[1]", 1),
    (
        {"patternProperties": {"^x$": False}},
        {"x": 1},
        "$.x",
        '$.patternProperties["^x$"]',
        1,
    ),
    ({"allOf": [False]}, 1, "$", "$.allOf[0]", 1),
    (
        {"dependencies": {"flag": False}},
        {"flag": True},
        "$",
        "$.dependencies.flag",
        {"flag": True},
    ),
]


def document(keyword, reference, target):
    return {
        keyword: [target] if keyword in {"enum", "examples"} else target,
        "$ref": reference,
    }


@pytest.mark.parametrize("keyword,reference", LITERAL_TARGETS)
@pytest.mark.parametrize("target,data,path,schema_path,value", FALSE_CONSTRAINTS)
def test_false_constraints_in_referenced_literals_keep_locations(
    keyword, reference, target, data, path, schema_path, value
):
    schema = document(keyword, reference, target)
    before = json.dumps(schema)
    failed = outputguard.validate(json.dumps(data), schema)
    assert not failed.valid
    assert len(failed.errors) == 1
    error = failed.errors[0]
    assert error.path == path
    assert error.schema_path == schema_path
    assert error.value == value
    assert error.message.startswith("False schema does not allow")
    assert json.dumps(schema) == before


@pytest.mark.parametrize("keyword,reference", LITERAL_TARGETS)
def test_boolean_literal_reference_targets(keyword, reference):
    for allowed in [True, False]:
        schema = document(keyword, reference, allowed)
        result = outputguard.validate("null", schema)
        assert result.valid is allowed
        if not allowed:
            assert result.errors[0].path == "$"
            assert result.errors[0].value is None


def test_referenced_literal_false_paths_within_embedded_resources():
    schema = {
        "definitions": {
            "resource": {
                "$id": "part.json",
                "definitions": {"holder": {"const": {"properties": {"blocked": False}}}},
                "properties": {"value": {"$ref": "#/definitions/holder/const"}},
            }
        },
        "$ref": "part.json",
    }
    failed = outputguard.validate('{"value":{"blocked":1}}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.value.blocked"
    assert failed.errors[0].value == 1


def test_nested_references_select_literals_from_a_root_without_a_reference():
    schema = {
        "default": {"properties": {"blocked": False}},
        "properties": {"value": {"$ref": "#/default"}},
    }
    failed = outputguard.validate('{"value":{"blocked":1}}', schema)
    assert failed.errors[0].path == "$.value.blocked"
    assert failed.errors[0].value == 1


def test_recursive_literal_references_keep_every_instance_path():
    schema = {
        "const": {
            "properties": {"blocked": False, "next": {"$ref": "#/const"}},
        },
        "$ref": "#/const",
    }
    failed = outputguard.validate('{"blocked":1,"next":{"blocked":2}}', schema)
    assert [error.path for error in failed.errors] == ["$.blocked", "$.next.blocked"]
    assert [error.value for error in failed.errors] == [1, 2]
    assert outputguard.validate('{"next":{}}', schema).valid


@pytest.mark.parametrize("name", ["$id", "$schema", "$ref", "const", "enum", "properties"])
def test_schema_keyword_names_remain_ordinary_property_names_in_literal_targets(name):
    schema = document("const", "#/const", {"properties": {name: False}})
    failed = outputguard.validate(json.dumps({name: 1}), schema)
    assert failed.errors[0].path == f"$.{name}"
    assert failed.errors[0].value == 1
    direct = document("const", f"#/const/properties/{name}", {"properties": {name: False}})
    assert not outputguard.validate("null", direct).valid


def test_literal_reference_siblings_follow_draft_seven():
    schema = {
        "const": {"$ref": "#/definitions/integer", "type": "string"},
        "definitions": {"integer": {"type": "integer"}},
        "$ref": "#/const",
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_literal_comparisons_survive_false_constraint_preparation_elsewhere():
    literal = {"properties": {"blocked": False}, "const": {"flag": False}}
    schema = {
        "definitions": {"holder": {"const": literal}},
        "allOf": [
            {"$ref": "#/definitions/holder"},
            {"properties": {"const": False}},
        ],
    }
    failed = outputguard.validate(json.dumps(literal), schema)
    assert len(failed.errors) == 1
    assert failed.errors[0].path == "$.const"
    assert failed.errors[0].value == {"flag": False}
    assert schema["definitions"]["holder"]["const"] is literal
    assert literal["properties"]["blocked"] is False


def test_non_false_diagnostics_keep_the_original_schema_representation():
    import jsonschema

    schema = {
        "allOf": [
            {"not": {"properties": {"blocked": False}}},
            {"properties": {"fail": False}},
        ]
    }
    data = {"fail": 1}
    native = next(
        error
        for error in jsonschema.Draft7Validator(schema).iter_errors(data)
        if error.validator == "not"
    )
    failed = outputguard.validate(json.dumps(data), schema)
    assert len(failed.errors) == 2
    assert native.message in [error.message for error in failed.errors]


def test_repairs_and_generation_feedback_preserve_literal_false_error_paths():
    schema = document("const", "#/const", {"properties": {"blocked": False}})
    repaired = outputguard.validate_and_repair('```json\n{"blocked":1}\n```', schema)
    assert repaired.repaired
    assert not repaired.valid
    assert repaired.errors[0].path == "$.blocked"
    with pytest.raises(outputguard.SchemaValidationError) as raised:
        outputguard.parse('{"blocked":1}', schema)
    assert raised.value.validation_errors[0].path == "$.blocked"

    def generate(prompt, context):
        if context.attempt:
            assert "$.blocked" in prompt
        return '{"blocked":1}' if not context.attempt else "{}"

    result = outputguard.guarded_generate(prompt="Return JSON", schema=schema, generate=generate)
    assert result.valid
    assert len(result.attempts) == 2


@pytest.mark.parametrize("keyword,reference", LITERAL_TARGETS)
def test_native_fixed_dependency_paths_are_used_for_literal_references(
    monkeypatch, keyword, reference
):
    import jsonschema

    import outputguard.schema as compatibility

    original = jsonschema.Draft7Validator.descend

    def fixed_descend(self, instance, schema, path=None, schema_path=None, resolver=None):
        for error in original(
            self, instance, schema, path=path, schema_path=schema_path, resolver=resolver
        ):
            if schema is False:
                if path is not None:
                    error.path.appendleft(path)
                if schema_path is not None:
                    error.schema_path.appendleft(schema_path)
            yield error

    if compatibility._NEEDS_FALSE_PATH_FIX:
        monkeypatch.setattr(jsonschema.Draft7Validator, "descend", fixed_descend)
    monkeypatch.setattr(compatibility, "_NEEDS_FALSE_PATH_FIX", False)
    schema = document(keyword, reference, {"properties": {"blocked": False}})
    assert compatibility.prepare_schema(schema) is schema
    failed = outputguard.validate('{"blocked":1}', schema)
    assert failed.errors[0].path == "$.blocked"
