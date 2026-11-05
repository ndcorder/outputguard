import json
from pathlib import Path

import pytest

from outputguard.validator import validate


@pytest.fixture
def simple_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "simple_schema.json").read_text())


@pytest.fixture
def nested_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "nested_schema.json").read_text())


def test_valid_json(simple_schema):
    result = validate('{"name": "Alice", "age": 30}', simple_schema)
    assert result.valid is True
    assert result.errors == []
    assert result.data == {"name": "Alice", "age": 30}


def test_invalid_type(simple_schema):
    result = validate('{"name": "Alice", "age": "thirty"}', simple_schema)
    assert result.valid is False
    assert len(result.errors) > 0
    assert any("age" in e.path for e in result.errors)


def test_missing_required(simple_schema):
    result = validate('{"name": "Alice"}', simple_schema)
    assert result.valid is False
    assert any("age" in e.message for e in result.errors)


def test_invalid_json():
    result = validate("not json at all", {"type": "object"})
    assert result.valid is False
    assert result.errors[0].path == "$"


def test_nested_schema_valid(nested_schema):
    text = json.dumps(
        {
            "items": [{"name": "Widget", "price": 9.99}],
            "metadata": {"total": 1, "timestamp": "2024-01-01"},
        }
    )
    result = validate(text, nested_schema)
    assert result.valid is True


def test_nested_schema_errors(nested_schema):
    text = json.dumps({"items": [{"name": "Widget", "price": "nine"}], "metadata": {"total": 1}})
    result = validate(text, nested_schema)
    assert result.valid is False
    assert len(result.errors) >= 2


@pytest.mark.parametrize(
    "key",
    [
        "0",
        "01",
        "12tail",
        "a.b",
        "a/b",
        "a~b",
        "a~1b",
        "",
        "a[0]",
        'a"b',
        "a\\b",
        "a\nb",
        "é",
        "😀",
        "a\n",
        "a\r",
        "a\u2028",
        "a\u2029",
    ],
)
def test_error_paths_quote_property_names(key):
    schema = {"type": "object", "properties": {key: {"type": "integer"}}}
    result = validate(json.dumps({key: "wrong"}), schema)
    assert not result.valid
    assert result.errors[0].path == f"$[{json.dumps(key, ensure_ascii=False)}]"
    assert result.errors[0].value == "wrong"
    assert (
        result.errors[0].schema_path == f"$.properties[{json.dumps(key, ensure_ascii=False)}].type"
    )


def test_error_paths_distinguish_numeric_properties_from_array_indexes():
    data = {"items": [{"0": ["wrong"]}]}
    schema = {
        "properties": {"items": {"items": {"properties": {"0": {"items": {"type": "integer"}}}}}}
    }
    result = validate(json.dumps(data), schema)
    assert result.errors[0].path == '$.items[0]["0"][0]'
    assert result.errors[0].value == "wrong"


def test_literal_property_and_nested_property_have_different_paths():
    schema = {
        "properties": {"a.b": {"type": "integer"}, "a": {"properties": {"b": {"type": "integer"}}}}
    }
    result = validate('{"a.b":"flat","a":{"b":"nested"}}', schema)
    assert {error.path: error.value for error in result.errors} == {
        '$["a.b"]': "flat",
        "$.a.b": "nested",
    }


def test_array_errors_sort_by_numeric_index():
    result = validate(json.dumps(["wrong"] * 12), {"items": {"type": "integer"}})
    assert [error.path for error in result.errors] == [f"$[{i}]" for i in range(12)]


@pytest.mark.parametrize(
    "format,text", [("python", '{0: "bad", "x": "bad"}'), ("yaml", "0: bad\nx: bad")]
)
def test_errors_with_mixed_mapping_keys_do_not_crash(format, text):
    result = validate(text, {"additionalProperties": {"type": "integer"}}, format=format)
    assert not result.valid
    assert len(result.errors) == 2


def test_retry_prompt_includes_unambiguous_property_path():
    import outputguard

    schema = {"properties": {"a/b": {"type": "integer"}}}
    result = validate('{"a/b":"wrong"}', schema)
    prompt = outputguard.retry_prompt(result.original_text, schema, result.errors)
    assert 'At $["a/b"]:' in prompt
