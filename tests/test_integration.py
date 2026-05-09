import json

import pytest
from pathlib import Path

from outputguard import validate_and_repair


@pytest.fixture
def simple_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "simple_schema.json").read_text())


@pytest.fixture
def nested_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "nested_schema.json").read_text())


def test_fenced_with_trailing_comma(simple_schema):
    text = '```json\n{"name": "Alice", "age": 30,}\n```'
    result = validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is True


def test_commentary_with_unquoted_keys(simple_schema):
    text = "Sure! Here's the JSON:\n{name: 'Bob', age: 25}\nLet me know!"
    result = validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is True
    assert result.data["name"] == "Bob"
    assert result.data["age"] == 25


def test_missing_closer(nested_schema):
    text = '{"items": [{"name": "Widget", "price": 9.99}], "metadata": {"total": 1, "timestamp": "2024-01-01"}'
    result = validate_and_repair(text, nested_schema)
    assert result.valid is True
    assert result.repaired is True


def test_multiple_real_world_issues(simple_schema):
    # Fenced + single quotes + trailing comma + unquoted keys
    text = "```json\n{name: 'Charlie', age: 35,}\n```"
    result = validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is True
    assert result.data["name"] == "Charlie"


def test_already_valid_passes_through(simple_schema):
    text = '{"name": "Diana", "age": 28}'
    result = validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is False
    assert result.data == {"name": "Diana", "age": 28}


def test_completely_broken():
    schema = {"type": "object"}
    result = validate_and_repair("This is just plain english text with no JSON whatsoever.", schema)
    assert result.valid is False
