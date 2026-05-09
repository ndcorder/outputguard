import pytest

from outputguard.exceptions import (
    OutputGuardError,
    ParseError,
    RepairError,
    SchemaValidationError,
    StrategyError,
)


def test_parse_error():
    err = ParseError("could not parse", original_text="bad json", parse_error="Expecting value")
    assert isinstance(err, OutputGuardError)
    assert err.original_text == "bad json"
    assert err.parse_error == "Expecting value"
    assert "could not parse" in str(err)


def test_schema_validation_error():
    err = SchemaValidationError(
        "schema mismatch",
        data={"a": 1},
        errors=[{"path": "$", "message": "missing required"}],
        schema={"type": "object"},
    )
    assert isinstance(err, OutputGuardError)
    assert err.data == {"a": 1}
    assert len(err.validation_errors) == 1


def test_repair_error():
    err = RepairError("failed", strategies_tried=["strip_fences", "fix_commas"], original_text="{bad}")
    assert isinstance(err, OutputGuardError)
    assert err.strategies_tried == ["strip_fences", "fix_commas"]


def test_strategy_error():
    err = StrategyError("boom", strategy_name="fix_quotes")
    assert isinstance(err, OutputGuardError)
    assert err.strategy_name == "fix_quotes"


def test_hierarchy():
    """All exceptions should be catchable with OutputGuardError."""
    with pytest.raises(OutputGuardError):
        raise ParseError("test", original_text="", parse_error=None)
    with pytest.raises(OutputGuardError):
        raise SchemaValidationError("test", data={}, errors=[], schema={})
    with pytest.raises(OutputGuardError):
        raise RepairError("test", strategies_tried=[], original_text="")
    with pytest.raises(OutputGuardError):
        raise StrategyError("test", strategy_name="")
