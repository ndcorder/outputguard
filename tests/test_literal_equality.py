import copy
import json

import pytest
from jsonschema import Draft7Validator

from outputguard import validate

KEYS = ["constructor", "valueOf", "toString", "__proto__"]
VALUES = [None, True, 0, "name", [], {}, {"nested": [1, False]}]


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("value", VALUES)
@pytest.mark.parametrize("keyword", ["const", "enum", "uniqueItems"])
@pytest.mark.parametrize("location", ["root", "property", "reference"])
def test_literal_equality_treats_method_and_prototype_names_as_data(key, value, keyword, location):
    literal = {key: value, "payload": [0, False]}
    changed = {key: value, "payload": [1, False]}
    if keyword == "uniqueItems":
        schema = {"uniqueItems": True}
        accepted, rejected = [literal, changed], [literal, copy.deepcopy(literal)]
    else:
        schema = {keyword: [None, literal] if keyword == "enum" else literal}
        accepted, rejected = literal, changed
    path = "$"
    if location == "property":
        schema = {"properties": {"entry": schema}}
        accepted, rejected = {"entry": accepted}, {"entry": rejected}
        path = "$.entry"
    elif location == "reference":
        schema = {"definitions": {"check": schema}, "$ref": "#/definitions/check"}
    before = copy.deepcopy(schema)
    assert validate(json.dumps(accepted), schema).valid
    result = validate(json.dumps(rejected), schema)
    assert not result.valid and result.parse_error is None
    assert [(error.path, error.value) for error in result.errors] == [
        (path, rejected["entry"] if location == "property" else rejected)
    ]
    assert result.errors[0].schema_path.endswith("." + keyword)
    assert schema == before


@pytest.mark.parametrize(
    "values,valid",
    [
        (["__proto__", "__proto__"], False),
        (["constructor", "constructor"], False),
        (["toString", "toString"], False),
        ([False, 0], True),
        ([True, 1], True),
        ([None, "null"], True),
        ([1, 1.0], False),
        ([0, -0.0], False),
        ([{"a": 1, "b": 2}, {"b": 2, "a": 1}], False),
        ([{"constructor": {}}, {"constructor": {"different": True}}], True),
    ],
)
def test_unique_items_compares_json_values(values, valid):
    assert validate(json.dumps(values), {"uniqueItems": True}).valid is valid


def test_native_python_literal_comparison_is_unchanged():
    literal = {"constructor": {}, "toString": []}
    assert Draft7Validator({"const": literal}).is_valid(copy.deepcopy(literal))
