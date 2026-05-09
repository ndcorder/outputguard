import json
import pytest
from pathlib import Path


@pytest.fixture
def simple_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "simple_schema.json").read_text())


@pytest.fixture
def nested_schema():
    return json.loads((Path(__file__).parent / "fixtures" / "nested_schema.json").read_text())


@pytest.fixture
def string_schema():
    return {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["text", "count"],
    }


@pytest.fixture
def enum_schema():
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
            "priority": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["status", "priority"],
    }
