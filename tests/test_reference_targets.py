import json
from urllib.parse import quote

import pytest
from referencing.exceptions import Unresolvable

from outputguard import validate

NON_SCHEMAS = [None, 0, 42, 1.5, "", "text", [], [True], [[False]]]


def document(target, location, encoded, suffix=""):
    if location == "resource":
        schema = {"definitions": {"part": {"$id": "folder/part.json", "default": target}}}
        base, path = "folder/part.json", "/default"
    elif location == "enum":
        schema = {"enum": [target]}
        base, path = "", "/enum/0"
    else:
        schema = {"default": target}
        base, path = "", "/default"
    schema["$ref"] = base + "#" + quote(path + suffix, safe="" if encoded else "/~")
    return schema


@pytest.mark.parametrize("target", NON_SCHEMAS)
@pytest.mark.parametrize("location", ["default", "enum", "resource"])
@pytest.mark.parametrize("encoded", [False, True])
def test_references_to_non_schema_values_raise_native_lookup_errors(target, location, encoded):
    schema = document(target, location, encoded)
    before = json.dumps(schema)
    for _ in range(2):
        with pytest.raises(Unresolvable):
            validate("42", schema)
    assert json.dumps(schema) == before


@pytest.mark.parametrize("target", [None, 42, "text", False, True])
@pytest.mark.parametrize("suffix", ["/0", "/not", "/$id"])
@pytest.mark.parametrize("encoded", [False, True])
def test_pointers_cannot_continue_through_scalars_or_booleans(target, suffix, encoded):
    with pytest.raises(Unresolvable):
        validate("42", document(target, "default", encoded, suffix))


@pytest.mark.parametrize("target", [True, False, {}, {"properties": {"blocked": False}}])
@pytest.mark.parametrize("location", ["default", "enum", "resource"])
@pytest.mark.parametrize("encoded", [False, True])
def test_schema_targets_preserve_validity_and_false_diagnostics(target, location, encoded):
    schema = document(target, location, encoded)
    assert validate("{}", schema).valid is (target is not False)
    failed = validate('{"blocked":42}', schema)
    if target is True or target == {}:
        assert failed.valid
    else:
        path, value = ("$", {"blocked": 42}) if target is False else ("$.blocked", 42)
        assert [(error.path, error.value) for error in failed.errors] == [(path, value)]
        assert "False schema" in failed.errors[0].message


def test_array_target_failure_identifies_its_escaped_document_location():
    schema = {"extension": {"a/b~c": []}, "$ref": "#/extension/a~1b~0c"}
    with pytest.raises(Unresolvable) as caught:
        validate("42", schema)
    assert caught.value.ref == "#/extension/a~1b~0c"


def test_target_guards_preserve_literal_comparisons_and_valid_descendants():
    literal = {"flag": False, "number": 42, "text": "text", "nested": [True]}
    schema = {
        "default": literal,
        "properties": {"literal": {"const": literal}, "value": {"$ref": "#/default/nested/0"}},
    }
    before = json.dumps(schema)
    assert validate(json.dumps({"literal": literal, "value": None}), schema).valid
    failed = validate(json.dumps({"literal": {**literal, "flag": 0}, "value": None}), schema)
    assert [error.path for error in failed.errors] == ["$.literal"]
    assert json.dumps(schema) == before
