import json

import jsonschema
import pytest
from referencing.exceptions import Unresolvable

from outputguard import validate

DIALECT = "http://json-schema.org/draft-07/schema#"


def evaluation_case(keyword, position, dialect, value):
    target = {"$id": "folder/check.json", "properties": {"value": {"$ref": "leaf.json"}}}
    parent = {
        "definitions": {
            "leaf": {"$id": "folder/leaf.json", "type": "integer"},
            "decoy": {"$id": "leaf.json", "type": "string"},
        }
    }
    if dialect in {"target", "all"}:
        target["$schema"] = DIALECT
    if dialect in {"parent", "all"}:
        parent["$schema"] = DIALECT
    if keyword == "if":
        parent.update({"if": target, "then": False, "else": True})
    elif keyword == "oneOf":
        parent["oneOf"] = [True, target]
    else:
        parent[keyword] = target
    data = [{"value": value}] if keyword == "contains" else {"value": value}
    if position == "property":
        schema, data = {"properties": {"payload": parent}}, {"payload": data}
    elif position == "resource":
        schema = {
            "definitions": {"parent": {"$id": "container/parent.json", **parent}},
            "$ref": "container/parent.json",
        }
    elif position == "annotation":
        resources = parent.pop("definitions")
        schema = {"definitions": resources, "default": parent, "$ref": "#%2Fdefault"}
    else:
        schema = parent
    if dialect == "all":
        schema["$schema"] = DIALECT
    matched = type(value) is int
    return schema, data, matched if keyword == "contains" else not matched


@pytest.mark.parametrize("keyword", ["if", "contains", "not", "oneOf"])
@pytest.mark.parametrize("position", ["root", "property", "resource", "annotation"])
@pytest.mark.parametrize("dialect", ["none", "target", "parent", "all"])
@pytest.mark.parametrize("value", [42, "wrong", False, None])
def test_boolean_evaluation_applies_resource_scope(keyword, position, dialect, value):
    schema, data, wanted = evaluation_case(keyword, position, dialect, value)
    before = json.dumps(schema)
    for _ in range(2):
        result = validate(json.dumps(data), schema)
        assert result.valid is wanted
        for error in result.errors:
            assert "allOf" not in error.schema_path
            assert "allOf" not in error.message
    assert json.dumps(schema) == before


@pytest.mark.parametrize("keyword", ["if", "contains", "not", "oneOf"])
@pytest.mark.parametrize("value", [42, "wrong"])
def test_evaluation_keeps_ids_beside_references_ignored(keyword, value):
    target = {"$id": "folder/ignored.json", "$ref": "leaf.json"}
    schema = {
        "definitions": {
            "leaf": {"$id": "leaf.json", "type": "integer"},
            "decoy": {"$id": "folder/leaf.json", "type": "string"},
        }
    }
    if keyword == "if":
        schema.update({"if": target, "then": False})
    elif keyword == "oneOf":
        schema[keyword] = [True, target]
    else:
        schema[keyword] = target
    data = [value] if keyword == "contains" else value
    assert validate(json.dumps(data), schema).valid is (
        type(value) is int if keyword == "contains" else type(value) is not int
    )


@pytest.mark.parametrize("keyword", ["if", "contains", "not", "oneOf"])
def test_missing_scoped_resource_stays_a_native_reference_error(keyword):
    schema, data, _ = evaluation_case(keyword, "root", "all", 42)
    del schema["definitions"]["leaf"]
    with pytest.raises(Unresolvable):
        validate(json.dumps(data), schema)


def test_scope_extension_does_not_modify_native_validators_or_dialect_registration():
    native_keywords = dict(jsonschema.Draft7Validator.VALIDATORS)
    native_evolve = jsonschema.Draft7Validator.evolve
    native_descend = jsonschema.Draft7Validator.descend
    schema, data, _ = evaluation_case("not", "property", "all", 42)
    assert not validate(json.dumps(data), schema).valid
    assert native_keywords == jsonschema.Draft7Validator.VALIDATORS
    assert jsonschema.Draft7Validator.evolve is native_evolve
    assert jsonschema.Draft7Validator.descend is native_descend
    assert jsonschema.validators.validator_for({"$schema": DIALECT}) is jsonschema.Draft7Validator
