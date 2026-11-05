import json
from urllib.parse import quote

import pytest
from referencing.exceptions import Unresolvable

from outputguard import validate, validate_and_repair

INVALID_INDEXES = ["01", "00", "-1", "-0", "+1", " 1", "1 ", "١", "１", "-", "2", "1.0", ""]
ARRAY_KEYWORDS = ["items", "allOf", "anyOf", "oneOf", "default", "enum", "examples", "extension"]


def pointer(*parts, encoded=False):
    path = "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)
    return "#" + quote(path, safe="" if encoded else "/~")


@pytest.mark.parametrize("keyword", ARRAY_KEYWORDS)
@pytest.mark.parametrize("index", INVALID_INDEXES)
@pytest.mark.parametrize("encoded", [False, True])
def test_array_pointer_indexes_reject_noncanonical_and_missing_tokens(keyword, index, encoded):
    schema = {
        keyword: [{"type": "integer"}, {"type": "string"}],
        "$ref": pointer(keyword, index, encoded=encoded),
    }
    before = json.dumps(schema)
    for _ in range(2):
        with pytest.raises(Unresolvable):
            validate("42", schema)
    assert json.dumps(schema) == before


@pytest.mark.parametrize("index", [*INVALID_INDEXES, "0", "1"])
@pytest.mark.parametrize("encoded", [False, True])
def test_object_pointer_keys_keep_their_literal_spelling(index, encoded):
    schema = {
        "definitions": {index: {"type": "integer"}},
        "$ref": pointer("definitions", index, encoded=encoded),
    }
    assert validate("42", schema).valid
    failed = validate('"wrong"', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$", "wrong")]


@pytest.mark.parametrize("keyword", ARRAY_KEYWORDS)
@pytest.mark.parametrize("encoded", [False, True])
def test_canonical_array_pointer_indexes_preserve_boolean_diagnostics(keyword, encoded):
    schema = {
        keyword: [{"properties": {"blocked": False}}, {"type": "integer"}],
        "$ref": pointer(keyword, "0", encoded=encoded),
    }
    assert validate("{}", schema).valid
    failed = validate('{"blocked":42}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.blocked", 42)]
    assert failed.errors[0].schema_path.endswith(".properties.blocked")
    assert "False schema" in failed.errors[0].message
    second = {**schema, "$ref": pointer(keyword, "1", encoded=encoded)}
    assert validate("42", second).valid
    assert not validate('"wrong"', second).valid


@pytest.mark.parametrize("index", ["0", "00", "-1", "-", "1"])
@pytest.mark.parametrize("encoded", [False, True])
def test_nested_array_pointers_keep_embedded_resource_scope(index, encoded):
    schema = {
        "definitions": {
            "part": {
                "$id": "folder/part.json",
                "default": [[{"properties": {"value": {"$ref": "leaf.json"}}}]],
                "definitions": {"leaf": {"$id": "leaf.json", "type": "integer"}},
            }
        },
        "$ref": "folder/part.json" + pointer("default", "0", index, encoded=encoded),
    }
    if index != "0":
        with pytest.raises(Unresolvable):
            validate('{"value":42}', schema)
        return
    assert validate('{"value":42}', schema).valid
    failed = validate('{"value":"wrong"}', schema)
    assert [(error.path, error.value) for error in failed.errors] == [("$.value", "wrong")]


def test_huge_array_index_is_a_lookup_failure_without_integer_conversion_overflow():
    schema = {"default": [{}], "$ref": "#/default/" + "9" * 10000}
    with pytest.raises(Unresolvable):
        validate("42", schema)


@pytest.mark.parametrize("index", ["9", "10", "11"])
def test_multidigit_array_indexes_select_their_exact_element(index):
    schema = {"default": [{"type": "integer"}] * 12, "$ref": "#/default/" + index}
    assert validate("42", schema).valid
    assert not validate('"wrong"', schema).valid


@pytest.mark.parametrize(
    ("reference", "unresolved"),
    [
        ("#/default/%30", False),
        ("#%2fdefault%2f%31", False),
        ("#/default/%30%31", True),
        ("#/default/%2B1", True),
        ("#/default/%201", True),
        ("#/default/%D9%A1", True),
    ],
)
def test_array_index_syntax_is_checked_after_uri_decoding(reference, unresolved):
    schema = {"default": [{"type": "integer"}, {"type": "integer"}], "$ref": reference}
    if unresolved:
        with pytest.raises(Unresolvable):
            validate("42", schema)
    else:
        assert validate("42", schema).valid
        assert not validate('"wrong"', schema).valid


def test_pointer_array_views_preserve_repaired_failure_feedback_and_caller_literals():
    literal = [{"properties": {"blocked": False}}]
    schema = {
        "default": literal,
        "properties": {"payload": {"$ref": "#/default/0"}, "literal": {"const": literal}},
    }
    before = json.dumps(schema)
    result = validate_and_repair(
        '```json\n{"payload":{"blocked":42},"literal":[{"properties":{"blocked":false}}]}\n```',
        schema,
    )
    assert result.repaired and not result.valid
    assert [(error.path, error.value) for error in result.errors] == [("$.payload.blocked", 42)]
    assert json.dumps(schema) == before
