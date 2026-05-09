import json

import pytest
from pathlib import Path

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
    result = validate('not json at all', {"type": "object"})
    assert result.valid is False
    assert result.errors[0].path == "$"


def test_nested_schema_valid(nested_schema):
    text = json.dumps({
        "items": [{"name": "Widget", "price": 9.99}],
        "metadata": {"total": 1, "timestamp": "2024-01-01"}
    })
    result = validate(text, nested_schema)
    assert result.valid is True


def test_nested_schema_errors(nested_schema):
    text = json.dumps({
        "items": [{"name": "Widget", "price": "nine"}],
        "metadata": {"total": 1}
    })
    result = validate(text, nested_schema)
    assert result.valid is False
    assert len(result.errors) >= 2
