import json
from urllib.parse import quote

import pytest
from referencing.exceptions import Unresolvable

from outputguard import validate


@pytest.mark.parametrize(
    "reference",
    [
        "#%2Fdefinitions%2Fpart",
        "#%2fdefinitions/part",
        "#/definitions%2Fpart",
        "#%2Fdefinitions/part",
    ],
)
def test_uri_encoded_pointer_separators_select_the_declared_schema(reference):
    schema = {"definitions": {"part": {"type": "integer"}}, "$ref": reference}
    before = json.dumps(schema)
    assert validate("42", schema).valid
    failed = validate('"wrong"', schema)
    assert not failed.valid
    assert [(error.path, error.value) for error in failed.errors] == [("$", "wrong")]
    assert json.dumps(schema) == before


@pytest.mark.parametrize(
    "name", ["part", "UPPER", "node:part", "node.part", "node-part", "node_part"]
)
def test_encoded_plain_names_resolve_valid_draft_seven_anchors(name):
    encoded = "".join(f"%{byte:02X}" for byte in name.encode())
    schema = {
        "definitions": {"part": {"$id": "#" + name, "type": "integer"}},
        "$ref": "#" + encoded,
    }
    assert validate("42", schema).valid
    assert not validate('"wrong"', schema).valid


@pytest.mark.parametrize("keyword", ["const", "enum", "default", "examples", "extension", "$async"])
@pytest.mark.parametrize("key", ["blocked", "__proto__", "a/b", "%2F", "é"])
def test_encoded_annotation_pointers_keep_false_instance_and_schema_locations(keyword, key):
    target = {"properties": {key: False}}
    array = keyword in {"enum", "examples"}
    pointer = "/" + keyword + ("/0" if array else "")
    schema = {keyword: [target] if array else target, "$ref": "#" + quote(pointer, safe="")}
    assert validate("{}", schema).valid
    failed = validate(json.dumps({key: 42}), schema)
    expected_path = "$" + (
        "." + key
        if key in {"blocked", "__proto__"}
        else "[" + json.dumps(key, ensure_ascii=False) + "]"
    )
    assert not failed.valid
    assert [(error.path, error.value) for error in failed.errors] == [(expected_path, 42)]
    assert failed.errors[0].schema_path.endswith(".properties" + expected_path[1:])
    assert "False schema" in failed.errors[0].message


@pytest.mark.parametrize("key", ["a/b", "a~b", "%2F", "%252F", "é", "__proto__", ""])
def test_pointer_tokens_are_unescaped_once_after_uri_decoding(key):
    token = key.replace("~", "~0").replace("/", "~1")
    reference = "#%2Fdefinitions%2F" + quote(token, safe="")
    schema = {"definitions": {key: {"type": "integer"}}, "$ref": reference}
    assert validate("42", schema).valid
    assert not validate('"wrong"', schema).valid


def test_encoded_references_preserve_literals_and_ignored_reference_siblings():
    literal = {"$ref": "#%2Fdefinitions%2Fpart", "type": "string"}
    schema = {
        "definitions": {"part": {"type": "integer"}},
        "default": literal,
        "properties": {"value": {"$ref": "#%2Fdefault"}, "literal": {"const": literal}},
    }
    before = json.dumps(schema)
    assert validate(json.dumps({"value": 42, "literal": literal}), schema).valid
    failed = validate(
        json.dumps({"value": 42, "literal": {**literal, "$ref": "#/definitions/part"}}), schema
    )
    assert not failed.valid
    assert failed.errors[0].path == "$.literal"
    assert json.dumps(schema) == before


def test_fragment_and_dependency_fallbacks_share_pointer_views_for_literal_targets():
    schema = {
        "dependencies": {
            "flag": ["needed"],
            "resource": {"$id": "part.json", "const": {"properties": {"blocked": False}}},
        },
        "$ref": "part.json#%2Fconst",
    }
    assert validate("{}", schema).valid
    failed = validate('{"blocked":42}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.blocked"
    assert failed.errors[0].schema_path.endswith(".properties.blocked")


def test_encoded_anchors_and_mixed_dependencies_keep_nested_literal_reference_views():
    schema = {
        "definitions": {
            "part": {"$id": "#part", "properties": {"value": {"$ref": "#/default"}}},
            "integer": {"type": "integer"},
        },
        "default": {"$ref": "#%2Fdefinitions%2Finteger", "type": "string"},
        "dependencies": {"flag": ["needed"], "unused": {"$id": "unused.json"}},
        "$ref": "#%70art",
    }
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]


def test_encoded_pointers_preserve_embedded_resource_scopes():
    schema = {
        "definitions": {
            "container": {
                "$id": "folder/container.json",
                "definitions": {"part": {"$id": "part.json", "type": "integer"}},
                "properties": {"value": {"$ref": "part.json"}},
            }
        },
        "$ref": "#%2Fdefinitions%2Fcontainer",
    }
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]


def test_recursive_encoded_pointers_keep_nested_false_diagnostics():
    schema = {
        "definitions": {
            "node": {
                "type": "object",
                "properties": {"next": {"$ref": "#%2Fdefinitions%2Fnode"}, "blocked": False},
            }
        },
        "$ref": "#%2Fdefinitions%2Fnode",
    }
    assert validate('{"next":{"next":{}}}', schema).valid
    failed = validate('{"next":{"blocked":42}}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.next.blocked", 42)]


@pytest.mark.parametrize(
    "reference", ["#%2Fdefinitions%2Fmissing", "#%6Dissing", "#%252Fdefinitions%252Fpart"]
)
def test_missing_encoded_targets_keep_native_lookup_exceptions(reference):
    with pytest.raises(Unresolvable):
        validate("42", {"definitions": {"part": {"type": "integer"}}, "$ref": reference})


def test_encoded_anchor_references_do_not_promote_later_draft_locations():
    with pytest.raises(Unresolvable):
        validate("42", {"$defs": {"part": {"$id": "#part", "type": "integer"}}, "$ref": "#%70art"})


@pytest.mark.parametrize(
    "keyword", ["definitions", "properties", "patternProperties", "dependencies"]
)
@pytest.mark.parametrize("key", ["%2F", "%252F", "%61", "a%b", "a%25b", "100%"])
@pytest.mark.parametrize("identifier", ["#part", "part.json"])
def test_resources_under_percent_named_schemas_remain_addressable(keyword, key, identifier):
    schema = {keyword: {key: {"$id": identifier, "type": "integer"}}, "$ref": identifier}
    before = json.dumps(schema)
    assert validate("42", schema).valid
    failed = validate('"wrong"', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$", "wrong")]
    assert json.dumps(schema) == before


@pytest.mark.parametrize(
    ("reference", "text"),
    [
        ("#number", "42"),
        ("#%6Eumber", "42"),
        ("#text", '"text"'),
        ("#/definitions/%252F", "42"),
        ("#/definitions/%25252F", '"text"'),
    ],
)
def test_internal_locations_cannot_alias_caller_pointer_encodings(reference, text):
    schema = {
        "definitions": {
            "%2F": {"$id": "#number", "type": "integer"},
            "%252F": {"$id": "#text", "type": "string"},
        },
        "$ref": reference,
    }
    assert validate(text, schema).valid
    failed = validate("false", schema)
    assert not failed.valid
    assert failed.errors[0].value is False
