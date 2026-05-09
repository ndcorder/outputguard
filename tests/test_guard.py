import json

import pytest
from pathlib import Path

from outputguard.guard import OutputGuard
from outputguard.exceptions import ParseError, SchemaValidationError


@pytest.fixture
def simple_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "simple_schema.json").read_text())


def test_validate_and_repair_repairable(simple_schema):
    guard = OutputGuard()
    text = '```json\n{"name": "Alice", "age": 30}\n```'
    result = guard.validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is True


def test_validate_and_repair_unrepairable(simple_schema):
    guard = OutputGuard()
    result = guard.validate_and_repair('totally broken nonsense', simple_schema)
    assert result.valid is False


def test_validate_and_repair_already_valid(simple_schema):
    guard = OutputGuard()
    text = '{"name": "Alice", "age": 30}'
    result = guard.validate_and_repair(text, simple_schema)
    assert result.valid is True
    assert result.repaired is False


def test_custom_strategies():
    guard = OutputGuard(strategies=["strip_fences"])
    result = guard.repair('```json\n{"a": 1}\n```')
    assert result.repaired is True
    assert "strip_fences" in result.strategies_applied


def test_parse_valid(simple_schema):
    guard = OutputGuard()
    data = guard.parse('{"name": "Alice", "age": 30}', simple_schema)
    assert data == {"name": "Alice", "age": 30}


def test_parse_repairable(simple_schema):
    guard = OutputGuard()
    data = guard.parse('```json\n{"name": "Alice", "age": 30}\n```', simple_schema)
    assert data["name"] == "Alice"


def test_parse_raises_parse_error():
    guard = OutputGuard()
    with pytest.raises(ParseError) as exc_info:
        guard.parse("totally broken nonsense", {"type": "object"})
    assert exc_info.value.original_text == "totally broken nonsense"


def test_parse_raises_schema_error(simple_schema):
    guard = OutputGuard()
    with pytest.raises(SchemaValidationError) as exc_info:
        guard.parse('{"name": "Alice"}', simple_schema)  # missing required age
    assert exc_info.value.data == {"name": "Alice"}
    assert len(exc_info.value.validation_errors) > 0


def test_repair_with_report():
    guard = OutputGuard()
    result, report = guard.repair('```json\n{"a": 1}\n```', report=True)
    assert result.repaired is True
    assert report.success is True
    assert report.confidence > 0
    assert "strip_fences" in report.strategies_applied
    assert report.diff != ""
