import json
from urllib.parse import quote

import pytest
from referencing.exceptions import Unresolvable

from outputguard import guarded_generate, validate, validate_and_repair

MAPS = ["definitions", "properties", "patternProperties", "dependencies"]
RESERVED = ["properties", "patternProperties", "definitions", "dependencies", "enum"]


def pointer(*parts):
    return "#/" + "/".join(
        quote(part.replace("~", "~0").replace("/", "~1"), safe="") for part in parts
    )


@pytest.mark.parametrize("metadata", [[], ["needed"], True, False, {"type": "null"}])
@pytest.mark.parametrize("encoded", [False, True])
def test_dependency_trigger_id_is_not_metadata_for_its_map(metadata, encoded):
    reference = "#%2Fdependencies%2Fpart" if encoded else "#/dependencies/part"
    schema = {"dependencies": {"$id": metadata, "part": {"type": "integer"}}, "$ref": reference}
    before = json.dumps(schema)
    assert validate("42", schema).valid
    failed = validate('"wrong"', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$", "wrong")]
    assert json.dumps(schema) == before


@pytest.mark.parametrize(
    "name", ["$id", "$ref", *RESERVED, "items", "const", "default", "__proto__", "a/b", "%2F", ""]
)
@pytest.mark.parametrize("forbidden", [False, True])
def test_map_children_keep_literal_names_and_false_constraints(name, forbidden):
    target = False if forbidden else {"type": "integer"}
    schema = {
        "dependencies": {"$id": ["needed"], name: target},
        "$ref": pointer("dependencies", name),
    }
    result = validate("42", schema)
    assert result.valid is (not forbidden)
    if forbidden:
        assert [(error.path, error.value) for error in result.errors] == [("$", 42)]
    assert not validate('"wrong"', schema).valid


@pytest.mark.parametrize("container", ["dependencies", "items", "tupleItems"])
@pytest.mark.parametrize("keyword", MAPS)
def test_nested_schema_map_keys_do_not_change_pointer_scope(container, keyword):
    target = {keyword: {"$id": {"type": "null"}, "value": {"type": "integer"}}}
    if container == "dependencies":
        schema, parts = {"dependencies": {"part": target}}, ["dependencies", "part"]
    elif container == "items":
        schema, parts = {"items": target}, ["items"]
    else:
        schema, parts = {"items": [target]}, ["items", "0"]
    schema["$ref"] = pointer(*parts, keyword, "value")
    assert validate("42", schema).valid
    assert not validate('"wrong"', schema).valid


@pytest.mark.parametrize("container", ["dependencies", "items", "tupleItems"])
@pytest.mark.parametrize("keyword", ["const", "default", "enum", "examples", "extension", "$async"])
def test_pointer_data_ids_are_ignored_after_dependencies_and_items(container, keyword):
    annotation = {
        "$id": "unregistered.json",
        "properties": {"value": {"$ref": "#/definitions/integer"}},
    }
    array = keyword in {"enum", "examples"}
    target = {keyword: [annotation] if array else annotation}
    if container == "dependencies":
        schema, parts = {"dependencies": {"part": target}}, ["dependencies", "part"]
    elif container == "items":
        schema, parts = {"items": target}, ["items"]
    else:
        schema, parts = {"items": [target]}, ["items", "0"]
    schema["definitions"] = {"integer": {"type": "integer"}}
    schema["$ref"] = pointer(*parts, keyword, *(["0"] if array else []))
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]


def test_pointer_data_descendants_remain_data_until_validation_enters_a_schema():
    annotation = {
        "properties": {
            "child": {
                "$id": "unregistered.json",
                "properties": {"value": {"$ref": "#/definitions/integer"}},
            }
        }
    }
    schema = {
        "definitions": {"integer": {"type": "integer"}},
        "dependencies": {"part": {"extension": annotation}},
    }
    # Direct traversal through an annotation does not establish child scopes.
    direct = {**schema, "$ref": "#/dependencies/part/extension/properties/child"}
    assert validate('{"value":42}', direct).valid
    # Validating its properties applies the child's real schema ID.
    with pytest.raises(Unresolvable):
        validate('{"child":{"value":42}}', {**schema, "$ref": "#/dependencies/part/extension"})


@pytest.mark.parametrize("keyword", MAPS)
def test_whole_maps_can_be_selected_as_schemas_without_changing_literal_values(keyword):
    schema = {keyword: {"const": {"flag": False}}, "$ref": "#%2F" + keyword}
    assert validate('{"flag":false}', schema).valid
    failed = validate('{"flag":0}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$", {"flag": 0})]


def resource():
    return {
        "$id": "folder/part.json",
        "definitions": {"value": {"$id": "value.json", "type": "integer"}},
        "properties": {"value": {"$ref": "value.json"}},
    }


@pytest.mark.parametrize("keyword", MAPS)
@pytest.mark.parametrize("name", RESERVED)
@pytest.mark.parametrize("by_id", [False, True])
def test_real_schema_ids_apply_to_children_with_keyword_names(keyword, name, by_id):
    schema = {
        keyword: {name: resource()},
        "$ref": "folder/part.json" if by_id else pointer(keyword, name),
    }
    before = json.dumps(schema)
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]
    assert json.dumps(schema) == before


@pytest.mark.parametrize("name", RESERVED)
def test_literal_property_constraints_keep_ids_and_closed_object_behavior(name):
    schema = {"properties": {name: resource()}, "additionalProperties": False}
    assert validate(json.dumps({name: {"value": 42}}), schema).valid
    assert not validate(json.dumps({name: {"value": "wrong"}}), schema).valid
    assert not validate(json.dumps({name: {"value": 42}, "extra": 0}), schema).valid


def test_shared_map_literals_remain_intact_when_references_require_scope_aliases():
    shared = {"properties": resource()}
    schema = {
        "definitions": shared,
        "properties": {"literal": {"const": shared}, "value": {"$ref": "#/definitions/properties"}},
    }
    before = json.dumps(schema)
    assert validate(json.dumps({"literal": shared, "value": {"value": 42}}), schema).valid
    changed = {"properties": {**shared["properties"], "$id": "wrong.json"}}
    failed = validate(json.dumps({"literal": changed, "value": {"value": 42}}), schema)
    assert failed.errors[0].path == "$.literal"
    assert json.dumps(schema) == before


def test_dependency_map_scopes_keep_repairs_and_generation_feedback():
    schema = {
        "dependencies": {"$id": ["needed"], "part": {"properties": {"value": False}}},
        "$ref": "#/dependencies/part",
    }
    text = '```json\n{"value":42}\n```'
    result = validate_and_repair(text, schema)
    assert not result.valid
    assert result.repaired
    assert result.data == {"value": 42}
    assert result.errors[0].path == "$.value"
    assert result.errors[0].schema_path.endswith(".properties.value")

    def generate(prompt, context):
        if context.attempt == 0:
            return text
        assert "$.value" in prompt
        assert context.previous_result.repaired
        assert context.previous_result.data == {"value": 42}
        return "{}"

    generated = guarded_generate(prompt="Return JSON", schema=schema, generate=generate)
    assert generated.valid
    assert generated.data == {}
    assert len(generated.attempts) == 2
    assert generated.attempts[0].result.errors[0].value == 42


@pytest.mark.parametrize("container", ["dependencies", "items", "tupleItems"])
@pytest.mark.parametrize("keyword", ["const", "default", "examples", "extension"])
def test_annotation_id_collisions_cannot_silently_select_another_resource(container, keyword):
    annotation = {"$id": "other.json", "properties": {"value": {"$ref": "#/definitions/integer"}}}
    array = keyword == "examples"
    target = {keyword: [annotation] if array else annotation}
    if container == "dependencies":
        schema, parts = {"dependencies": {"part": target}}, ["dependencies", "part"]
    elif container == "items":
        schema, parts = {"items": target}, ["items"]
    else:
        schema, parts = {"items": [target]}, ["items", "0"]
    schema["definitions"] = {
        "integer": {"type": "integer"},
        "other": {"$id": "other.json", "definitions": {"integer": {"type": "string"}}},
    }
    schema["$ref"] = pointer(*parts, keyword, *(["0"] if array else []))
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]


def test_selected_data_schemas_apply_real_conditional_subschema_ids():
    schema = {
        "definitions": {
            "integer": {"type": "integer"},
            "other": {"$id": "other.json", "definitions": {"integer": {"type": "string"}}},
        },
        "dependencies": {
            "part": {
                "extension": {
                    "if": True,
                    "then": {
                        "$id": "other.json",
                        "properties": {"value": {"$ref": "#/definitions/integer"}},
                    },
                }
            }
        },
        "$ref": "#%2Fdependencies%2Fpart%2Fextension",
    }
    assert validate('{"value":"text"}', schema).valid
    assert not validate('{"value":42}', schema).valid


def test_map_role_is_fresh_when_an_earlier_lookup_activated_the_map_as_a_schema():
    schema = {
        "definitions": {
            "integer": {"type": "integer"},
            "const": {
                "$id": "other.json",
                "definitions": {"integer": {"type": "string"}},
                "properties": {"value": {"$ref": "#/definitions/integer"}},
            },
        },
        "properties": {
            "first": {"$ref": "#/definitions"},
            "second": {"$ref": "#/definitions/const"},
        },
    }
    first = validate('{"first":0,"second":{"value":"text"}}', schema)
    assert [(error.path, error.value) for error in first.errors] == [("$.first", 0)]
    second = validate('{"first":0,"second":{"value":42}}', schema)
    assert [(error.path, error.value) for error in second.errors] == [
        ("$.first", 0),
        ("$.second.value", 42),
    ]


@pytest.mark.parametrize(
    "location",
    [
        *MAPS,
        "allOf",
        "anyOf",
        "oneOf",
        "items",
        "tupleItems",
        "additionalItems",
        "additionalProperties",
        "contains",
        "propertyNames",
        "not",
        "if",
        "then",
        "else",
    ],
)
def test_declared_resources_keep_pointer_roles_from_every_schema_location(location):
    node = {
        "$id": "part.json",
        "definitions": {"integer": {"type": "integer"}},
        "dependencies": {
            "part": {
                "extension": {
                    "$id": "other.json",
                    "properties": {"value": {"$ref": "#/definitions/integer"}},
                }
            }
        },
    }
    if location in MAPS:
        value = {"resource": node}
    elif location in {"allOf", "anyOf", "oneOf", "tupleItems"}:
        value = [node]
    else:
        value = node
    schema = {
        "items" if location == "tupleItems" else location: value,
        "$ref": "part.json#/dependencies/part/extension",
    }
    schema.setdefault("definitions", {})["other"] = {
        "$id": "other.json",
        "definitions": {"integer": {"type": "string"}},
    }
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]
