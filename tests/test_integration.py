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


def test_python_dict_output(simple_schema):
    text = "{'name': 'Frank', 'age': 45}"
    result = validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.data["name"] == "Frank"


def test_python_booleans(simple_schema):
    schema = {
        "type": "object",
        "properties": {"active": {"type": "boolean"}, "name": {"type": "string"}},
        "required": ["active", "name"],
    }
    text = "{'active': True, 'name': 'Test'}"
    result = validate_and_repair(text, schema)
    assert result.valid is True
    assert result.data["active"] is True


def test_truncated_json(nested_schema):
    text = '{"items": [{"name": "Widget", "price": 9.99}], "metadata": {"total": 1, "timestamp": "2024-01-01"'
    result = validate_and_repair(text, nested_schema)
    assert result.valid is True


def test_parse_convenience():
    import outputguard

    schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]}
    data = outputguard.parse('```json\n{"x": 42}\n```', schema)
    assert data == {"x": 42}


def test_parse_raises_on_garbage():
    import outputguard
    from outputguard.exceptions import ParseError
    import pytest

    with pytest.raises(ParseError):
        outputguard.parse("not json", {"type": "object"})


def test_repair_report_integration():
    from outputguard.repairer import repair

    result, report = repair('```json\n{"a": 1,}\n```', report=True)
    assert result.repaired is True
    assert report.success is True
    assert report.confidence > 0
    assert len(report.strategies_applied) >= 1
    assert report.diff != ""
    assert "No repair needed" not in report.summary


def test_kitchen_sink(simple_schema):
    """Every common LLM failure mode combined."""
    text = """Sure! Here's the user data:

```json
{
    name: 'Zara', // the user's name
    age: 28, /* years old */
    active: True,
}
```

Let me know if you need anything else!"""
    result = validate_and_repair(
        text,
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "active": {"type": "boolean"},
            },
            "required": ["name", "age"],
        },
    )
    assert result.valid is True
    assert result.data["name"] == "Zara"
    assert result.data["age"] == 28
    assert result.data["active"] is True
