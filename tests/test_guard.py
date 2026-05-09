import json

import pytest
from pathlib import Path

from outputguard.guard import OutputGuard


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
