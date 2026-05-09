"""Exhaustive API contract tests for outputguard public surfaces.

Covers: parse, validate, repair, validate_and_repair, retry_prompt,
OutputGuard class, exceptions, RepairReport, strategy registry, and CLI.
"""

import json
import os
import tempfile

import pytest
from click.testing import CliRunner

# ── Public top-level API ──────────────────────────────────────────────
from outputguard import (
    OutputGuard,
    parse,
    repair,
    retry_prompt,
    validate,
    validate_and_repair,
)
from outputguard.cli import cli
from outputguard.exceptions import (
    OutputGuardError,
    ParseError,
    RepairError,
    SchemaValidationError,
    StrategyError,
)
from outputguard.models import RepairResult, ValidationError, ValidationResult
from outputguard.repairer import repair as raw_repair
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import (
    ALL_STRATEGIES,
    STRATEGY_DESCRIPTIONS,
    get_strategies,
    get_strategy,
)

# ─────────────────────────────────────────────────────────────────────
# Shared schemas
# ─────────────────────────────────────────────────────────────────────

OBJECT_SCHEMA = {"type": "object"}
ARRAY_SCHEMA = {"type": "array"}
SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}
NESTED_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                },
                "required": ["name", "price"],
            },
        },
    },
    "required": ["items"],
}
ENUM_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["active", "inactive", "pending"]},
        "priority": {"type": "integer", "minimum": 1, "maximum": 5},
    },
    "required": ["status", "priority"],
}
NUMBER_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": "number", "minimum": 0, "maximum": 100},
    },
    "required": ["value"],
}
STRING_PATTERN_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "pattern": "^[A-Z]{3}$"},
    },
    "required": ["code"],
}


# ═════════════════════════════════════════════════════════════════════
# Class 1 — TestParseFunction (25 cases)
# ═════════════════════════════════════════════════════════════════════


class TestParseFunction:
    """Tests for the top-level parse() function."""

    def test_parse_returns_dict(self):
        data = parse('{"a": 1}', OBJECT_SCHEMA)
        assert isinstance(data, dict)
        assert data == {"a": 1}

    def test_parse_returns_list(self):
        data = parse("[1, 2, 3]", ARRAY_SCHEMA)
        assert isinstance(data, list)
        assert data == [1, 2, 3]

    def test_parse_repairs_then_returns(self):
        data = parse('```json\n{"a": 1}\n```', OBJECT_SCHEMA)
        assert data == {"a": 1}

    def test_parse_raises_parse_error_on_garbage(self):
        with pytest.raises(ParseError) as exc:
            parse("not json", OBJECT_SCHEMA)
        assert exc.value.original_text == "not json"
        assert exc.value.parse_error is not None

    def test_parse_raises_schema_error(self):
        with pytest.raises(SchemaValidationError) as exc:
            parse('{"a": 1}', {"type": "object", "required": ["b"]})
        assert exc.value.data == {"a": 1}
        assert len(exc.value.validation_errors) > 0
        assert exc.value.schema == {"type": "object", "required": ["b"]}

    def test_parse_error_is_outputguard_error(self):
        with pytest.raises(OutputGuardError):
            parse("garbage", OBJECT_SCHEMA)

    def test_schema_error_is_outputguard_error(self):
        with pytest.raises(OutputGuardError):
            parse('{"a": 1}', {"type": "object", "required": ["b"]})

    def test_parse_with_nested_object(self):
        text = json.dumps({"items": [{"name": "x", "price": 1.0}]})
        data = parse(text, NESTED_SCHEMA)
        assert data["items"][0]["name"] == "x"

    def test_parse_with_enum_schema(self):
        text = json.dumps({"status": "active", "priority": 3})
        data = parse(text, ENUM_SCHEMA)
        assert data["status"] == "active"

    def test_parse_rejects_invalid_enum(self):
        with pytest.raises(SchemaValidationError):
            parse('{"status": "unknown", "priority": 3}', ENUM_SCHEMA)

    def test_parse_rejects_number_out_of_range(self):
        with pytest.raises(SchemaValidationError):
            parse('{"value": 200}', NUMBER_SCHEMA)

    def test_parse_accepts_number_in_range(self):
        data = parse('{"value": 50}', NUMBER_SCHEMA)
        assert data["value"] == 50

    def test_parse_rejects_bad_pattern(self):
        with pytest.raises(SchemaValidationError):
            parse('{"code": "abc"}', STRING_PATTERN_SCHEMA)  # lowercase

    def test_parse_accepts_good_pattern(self):
        data = parse('{"code": "ABC"}', STRING_PATTERN_SCHEMA)
        assert data["code"] == "ABC"

    def test_parse_empty_object_matches_empty_schema(self):
        data = parse("{}", OBJECT_SCHEMA)
        assert data == {}

    def test_parse_empty_array_matches_array_schema(self):
        data = parse("[]", ARRAY_SCHEMA)
        assert data == []

    def test_parse_with_trailing_comma_repair(self):
        data = parse('{"a": 1,}', OBJECT_SCHEMA)
        assert data == {"a": 1}

    def test_parse_with_single_quotes_repair(self):
        data = parse("{'a': 1}", OBJECT_SCHEMA)
        assert data == {"a": 1}

    def test_parse_with_unquoted_keys_repair(self):
        data = parse("{a: 1}", OBJECT_SCHEMA)
        assert data == {"a": 1}

    def test_parse_repairs_but_still_fails_schema(self):
        """Valid JSON that doesn't match the schema raises SchemaValidationError."""
        with pytest.raises(SchemaValidationError) as exc:
            parse('{"x": 1}', SIMPLE_SCHEMA)  # missing name and age
        assert exc.value.data == {"x": 1}

    def test_parse_preserves_data_types(self):
        text = json.dumps({"name": "Jo", "age": 25})
        data = parse(text, SIMPLE_SCHEMA)
        assert isinstance(data["name"], str)
        assert isinstance(data["age"], int)

    def test_parse_boolean_values(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
        data = parse('{"ok": true}', schema)
        assert data["ok"] is True

    def test_parse_null_value(self):
        schema = {"type": "object", "properties": {"x": {"type": ["string", "null"]}}}
        data = parse('{"x": null}', schema)
        assert data["x"] is None

    def test_parse_deeply_nested(self):
        schema = {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "properties": {
                        "b": {"type": "object", "properties": {"c": {"type": "integer"}}}
                    },
                }
            },
        }
        data = parse('{"a": {"b": {"c": 42}}}', schema)
        assert data["a"]["b"]["c"] == 42

    def test_parse_error_message_is_str(self):
        with pytest.raises(ParseError) as exc:
            parse("xxx", OBJECT_SCHEMA)
        assert isinstance(str(exc.value), str)
        assert len(str(exc.value)) > 0


# ═════════════════════════════════════════════════════════════════════
# Class 2 — TestValidationResult (18 cases)
# ═════════════════════════════════════════════════════════════════════


class TestValidationResult:
    """Tests for the ValidationResult dataclass returned by validate()."""

    def test_valid_result_fields(self):
        result = validate('{"a": 1}', OBJECT_SCHEMA)
        assert result.valid is True
        assert result.data == {"a": 1}
        assert result.errors == []
        assert result.repaired is False
        assert result.strategies_applied == []
        assert result.original_text == '{"a": 1}'
        assert result.repaired_text == ""

    def test_invalid_result_has_errors(self):
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        result = validate('{"a": "x"}', schema)
        assert result.valid is False
        assert len(result.errors) > 0
        assert result.errors[0].path != ""
        assert result.errors[0].message != ""

    def test_repair_result_fields_via_validate_and_repair(self):
        result = validate_and_repair('```json\n{"a": 1}\n```', OBJECT_SCHEMA)
        assert result.valid is True
        assert result.repaired is True
        assert len(result.strategies_applied) > 0
        assert result.original_text == '```json\n{"a": 1}\n```'
        assert result.repaired_text != ""
        assert result.repaired_text != result.original_text

    def test_multiple_validation_errors(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "string"}},
            "required": ["a", "b"],
        }
        result = validate('{"a": "wrong", "b": 123}', schema)
        assert not result.valid
        assert len(result.errors) >= 2

    def test_error_paths_nested(self):
        schema = {
            "type": "object",
            "properties": {"items": {"type": "array", "items": {"type": "integer"}}},
        }
        result = validate('{"items": [1, "two", 3]}', schema)
        assert any("items" in e.path for e in result.errors)

    def test_valid_result_data_is_parsed(self):
        result = validate('{"x": [1, 2]}', OBJECT_SCHEMA)
        assert result.data == {"x": [1, 2]}

    def test_invalid_json_result(self):
        result = validate("not json", OBJECT_SCHEMA)
        assert result.valid is False
        assert result.data is None
        assert len(result.errors) == 1

    def test_result_is_dataclass(self):
        result = validate("{}", OBJECT_SCHEMA)
        assert isinstance(result, ValidationResult)

    def test_validation_error_has_value_field(self):
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        result = validate('{"a": "text"}', schema)
        assert result.errors[0].value == "text"

    def test_validation_error_schema_path(self):
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        result = validate('{"a": "text"}', schema)
        assert result.errors[0].schema_path != ""

    def test_valid_array_schema(self):
        result = validate("[1, 2, 3]", ARRAY_SCHEMA)
        assert result.valid is True
        assert result.data == [1, 2, 3]

    def test_type_mismatch_root(self):
        result = validate("[1, 2]", OBJECT_SCHEMA)
        assert result.valid is False

    def test_additional_properties_allowed_by_default(self):
        result = validate('{"name": "x", "age": 1, "extra": true}', SIMPLE_SCHEMA)
        assert result.valid is True

    def test_missing_required_field(self):
        result = validate('{"name": "x"}', SIMPLE_SCHEMA)
        assert result.valid is False
        assert any("age" in e.message for e in result.errors)

    def test_validate_preserves_original_text(self):
        text = '{"a":   1  }'
        result = validate(text, OBJECT_SCHEMA)
        assert result.original_text == text

    def test_validate_and_repair_already_valid(self):
        result = validate_and_repair('{"a": 1}', OBJECT_SCHEMA)
        assert result.valid is True
        assert result.repaired is False
        assert result.strategies_applied == []

    def test_validate_and_repair_unrepairable(self):
        result = validate_and_repair("total garbage here", OBJECT_SCHEMA)
        assert result.valid is False

    def test_validate_and_repair_repaired_text_is_valid_json(self):
        result = validate_and_repair('```json\n{"x": 1}\n```', OBJECT_SCHEMA)
        assert result.valid
        parsed = json.loads(result.repaired_text)
        assert parsed == {"x": 1}


# ═════════════════════════════════════════════════════════════════════
# Class 3 — TestRepairResult (12 cases)
# ═════════════════════════════════════════════════════════════════════


class TestRepairResult:
    """Tests for the RepairResult dataclass returned by repair()."""

    def test_result_not_repaired(self):
        result = repair('{"a": 1}')
        assert result.repaired is False
        assert result.text == '{"a": 1}'
        assert result.strategies_applied == []
        assert result.parse_error is None

    def test_result_repaired(self):
        result = repair('```json\n{"a": 1}\n```')
        assert result.repaired is True
        assert "strip_fences" in result.strategies_applied
        assert result.parse_error is None

    def test_result_failed(self):
        result = repair("totally broken")
        assert result.repaired is False
        assert result.parse_error is not None
        assert isinstance(result.parse_error, str)

    def test_result_is_dataclass(self):
        result = repair('{"a": 1}')
        assert isinstance(result, RepairResult)

    def test_repaired_text_is_valid_json(self):
        result = repair('```json\n{"a": 1}\n```')
        assert result.repaired
        parsed = json.loads(result.text)
        assert parsed == {"a": 1}

    def test_unrepaired_text_preserved(self):
        original = "totally broken"
        result = repair(original)
        assert result.text == original

    def test_strategies_applied_is_list(self):
        result = repair('{"a": 1}')
        assert isinstance(result.strategies_applied, list)

    def test_repair_trailing_comma(self):
        result = repair('{"a": 1,}')
        assert result.repaired
        assert "fix_commas" in result.strategies_applied

    def test_repair_single_quotes(self):
        result = repair("{'a': 1}")
        assert result.repaired
        assert "fix_quotes" in result.strategies_applied

    def test_repair_unquoted_keys(self):
        result = repair("{a: 1}")
        assert result.repaired
        assert "fix_keys" in result.strategies_applied

    def test_repair_multiple_issues(self):
        result = repair("```json\n{a: 'hello',}\n```")
        assert result.repaired
        assert len(result.strategies_applied) >= 2

    def test_repair_empty_string_fails(self):
        result = repair("")
        assert result.repaired is False


# ═════════════════════════════════════════════════════════════════════
# Class 4 — TestRepairReport (18 cases)
# ═════════════════════════════════════════════════════════════════════


class TestRepairReport:
    """Tests for RepairReport via raw_repair(report=True)."""

    def test_report_from_repairer(self):
        result, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        assert result.repaired
        assert report.success
        assert len(report.steps) > 0
        assert report.original_text == '```json\n{"a": 1}\n```'
        assert report.final_text == '{"a": 1}'

    def test_report_confidence_range(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        assert 0 <= report.confidence <= 1

    def test_report_confidence_positive_for_single_strategy(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        assert report.confidence >= 0.5

    def test_report_confidence_lower_for_many_strategies(self):
        _, report = raw_repair("```json\n{name: 'x', val: 1,}\n```", report=True)
        assert report.confidence < 1.0

    def test_report_confidence_zero_on_failure(self):
        _, report = raw_repair("garbage", report=True)
        assert report.confidence == 0

    def test_report_confidence_one_for_valid(self):
        _, report = raw_repair('{"a": 1}', report=True)
        assert report.confidence == 1.0

    def test_report_diff_present(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        diff = report.diff
        assert "original" in diff or "---" in diff

    def test_report_no_diff_for_valid(self):
        _, report = raw_repair('{"a": 1}', report=True)
        assert report.diff == ""

    def test_report_summary_contains_strategy(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        summary = report.summary
        assert "strip_fences" in summary

    def test_report_summary_for_valid(self):
        _, report = raw_repair('{"a": 1}', report=True)
        assert "valid" in report.summary.lower() or "No repair" in report.summary

    def test_report_summary_for_failure(self):
        _, report = raw_repair("garbage", report=True)
        assert "fail" in report.summary.lower()

    def test_report_step_diffs_multi_strategy(self):
        _, report = raw_repair("```json\n{name: 'x',}\n```", report=True)
        step_diffs = report.step_diffs()
        assert "===" in step_diffs

    def test_report_strategies_applied_list(self):
        _, report = raw_repair("```json\n{name: 'x',}\n```", report=True)
        applied = report.strategies_applied
        assert "strip_fences" in applied
        assert isinstance(applied, list)

    def test_report_strategies_tried_list(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        assert isinstance(report.strategies_tried, list)
        assert len(report.strategies_tried) >= len(report.strategies_applied)

    def test_report_success_flag_on_failure(self):
        _, report = raw_repair("garbage", report=True)
        assert report.success is False

    def test_report_parse_error_on_failure(self):
        _, report = raw_repair("garbage", report=True)
        assert report.parse_error is not None
        assert isinstance(report.parse_error, str)

    def test_report_steps_are_strategy_applications(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        for step in report.steps:
            assert isinstance(step, StrategyApplication)
            assert isinstance(step.name, str)
            assert isinstance(step.changed, bool)

    def test_strategy_application_diff_property(self):
        _, report = raw_repair('```json\n{"a": 1}\n```', report=True)
        changed_steps = [s for s in report.steps if s.changed]
        assert len(changed_steps) > 0
        for step in changed_steps:
            assert step.diff != ""


# ═════════════════════════════════════════════════════════════════════
# Class 5 — TestStrategyRegistry (12 cases)
# ═════════════════════════════════════════════════════════════════════


class TestStrategyRegistry:
    """Tests for strategy module: ALL_STRATEGIES, get_strategy, etc."""

    def test_all_strategies_count(self):
        assert len(ALL_STRATEGIES) == 14

    def test_all_strategies_have_descriptions(self):
        for name, _fn in ALL_STRATEGIES:
            assert name in STRATEGY_DESCRIPTIONS
            assert len(STRATEGY_DESCRIPTIONS[name]) > 0

    def test_get_strategy_by_name(self):
        fn = get_strategy("strip_fences")
        assert callable(fn)

    def test_get_strategy_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            get_strategy("nonexistent")

    def test_get_strategies_none_returns_all(self):
        strategies = get_strategies(None)
        assert len(strategies) == 14

    def test_get_strategies_subset(self):
        strategies = get_strategies(["strip_fences", "fix_commas"])
        assert len(strategies) == 2
        names = [n for n, _ in strategies]
        assert "strip_fences" in names
        assert "fix_commas" in names

    def test_get_strategies_empty_list(self):
        strategies = get_strategies([])
        assert len(strategies) == 0

    def test_strategy_functions_are_callable(self):
        for _name, fn in ALL_STRATEGIES:
            assert callable(fn)

    def test_strategy_handles_empty_string(self):
        for name, fn in ALL_STRATEGIES:
            result = fn("")
            assert isinstance(result, str), f"Strategy {name} did not return str"

    def test_all_strategies_are_tuples(self):
        for entry in ALL_STRATEGIES:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            name, fn = entry
            assert isinstance(name, str)

    def test_strategy_descriptions_keys_match(self):
        strategy_names = {n for n, _ in ALL_STRATEGIES}
        desc_names = set(STRATEGY_DESCRIPTIONS.keys())
        assert strategy_names == desc_names

    def test_strategy_order_strip_fences_first(self):
        assert ALL_STRATEGIES[0][0] == "strip_fences"


# ═════════════════════════════════════════════════════════════════════
# Class 6 — TestOutputGuardClass (15 cases)
# ═════════════════════════════════════════════════════════════════════


class TestOutputGuardClass:
    """Tests for the OutputGuard class API."""

    def test_default_guard_validate(self):
        guard = OutputGuard()
        result = guard.validate('{"a": 1}', OBJECT_SCHEMA)
        assert result.valid

    def test_custom_strategies_ignores_others(self):
        guard = OutputGuard(strategies=["strip_fences"])
        result = guard.repair("{'a': 1}")  # needs fix_quotes
        assert not result.repaired

    def test_custom_strategies_applies_selected(self):
        guard = OutputGuard(strategies=["strip_fences"])
        result = guard.repair('```json\n{"a": 1}\n```')
        assert result.repaired

    def test_max_repair_attempts(self):
        guard = OutputGuard(max_repair_attempts=1)
        result = guard.validate_and_repair('```json\n{"a": 1}\n```', OBJECT_SCHEMA)
        assert result.valid

    def test_parse_method(self):
        guard = OutputGuard()
        data = guard.parse('{"a": 1}', OBJECT_SCHEMA)
        assert data == {"a": 1}

    def test_parse_method_raises_parse_error(self):
        guard = OutputGuard()
        with pytest.raises(ParseError):
            guard.parse("garbage", OBJECT_SCHEMA)

    def test_parse_method_raises_schema_error(self):
        guard = OutputGuard()
        with pytest.raises(SchemaValidationError):
            guard.parse('{"a": 1}', {"type": "object", "required": ["b"]})

    def test_retry_prompt_method(self):
        guard = OutputGuard()
        errors = [ValidationError(message="missing field", path="$.name", schema_path="required")]
        prompt = guard.retry_prompt("{}", SIMPLE_SCHEMA, errors)
        assert "name" in prompt
        assert "missing" in prompt.lower()

    def test_validate_and_repair_method(self):
        guard = OutputGuard()
        result = guard.validate_and_repair('```json\n{"a": 1}\n```', OBJECT_SCHEMA)
        assert result.valid
        assert result.repaired

    def test_repair_with_report(self):
        guard = OutputGuard()
        result, report = guard.repair('```json\n{"a": 1}\n```', report=True)
        assert result.repaired
        assert isinstance(report, RepairReport)
        assert report.success

    def test_repair_without_report(self):
        guard = OutputGuard()
        result = guard.repair('{"a": 1}')
        assert isinstance(result, RepairResult)

    def test_default_max_repair_attempts(self):
        guard = OutputGuard()
        assert guard.max_repair_attempts == 3

    def test_default_strategies_is_none(self):
        guard = OutputGuard()
        assert guard.strategies is None

    def test_guard_validate_invalid(self):
        guard = OutputGuard()
        result = guard.validate("not json", OBJECT_SCHEMA)
        assert result.valid is False

    def test_guard_repair_valid_json(self):
        guard = OutputGuard()
        result = guard.repair('{"x": 1}')
        assert not result.repaired
        assert result.text == '{"x": 1}'


# ═════════════════════════════════════════════════════════════════════
# Class 7 — TestRetryPrompt (12 cases)
# ═════════════════════════════════════════════════════════════════════


class TestRetryPrompt:
    """Tests for the retry_prompt() function."""

    def test_prompt_contains_errors(self):
        errors = [
            ValidationError(message="wrong type", path="$.age", schema_path="properties.age.type")
        ]
        prompt = retry_prompt('{"age": "thirty"}', OBJECT_SCHEMA, errors)
        assert "$.age" in prompt
        assert "wrong type" in prompt

    def test_prompt_contains_schema_info(self):
        errors = [ValidationError(message="missing", path="$", schema_path="required")]
        prompt = retry_prompt("{}", SIMPLE_SCHEMA, errors)
        assert "name" in prompt

    def test_prompt_truncates_long_input(self):
        long_text = '{"x": "' + "a" * 1000 + '"}'
        errors = [ValidationError(message="err", path="$", schema_path="")]
        prompt = retry_prompt(long_text, OBJECT_SCHEMA, errors)
        assert "..." in prompt

    def test_prompt_has_return_instruction(self):
        errors = [ValidationError(message="err", path="$", schema_path="")]
        prompt = retry_prompt("{}", OBJECT_SCHEMA, errors)
        assert "Return ONLY" in prompt or "return only" in prompt.lower()

    def test_prompt_is_string(self):
        errors = [ValidationError(message="err", path="$", schema_path="")]
        prompt = retry_prompt("{}", OBJECT_SCHEMA, errors)
        assert isinstance(prompt, str)

    def test_prompt_multiple_errors(self):
        errors = [
            ValidationError(message="err1", path="$.a", schema_path="p1"),
            ValidationError(message="err2", path="$.b", schema_path="p2"),
        ]
        prompt = retry_prompt("{}", OBJECT_SCHEMA, errors)
        assert "err1" in prompt
        assert "err2" in prompt

    def test_prompt_empty_errors(self):
        prompt = retry_prompt("{}", OBJECT_SCHEMA, [])
        assert isinstance(prompt, str)

    def test_prompt_includes_original_output(self):
        errors = [ValidationError(message="err", path="$", schema_path="")]
        prompt = retry_prompt('{"key": "value"}', OBJECT_SCHEMA, errors)
        assert "key" in prompt

    def test_prompt_short_input_not_truncated(self):
        short_text = '{"a": 1}'
        errors = [ValidationError(message="err", path="$", schema_path="")]
        prompt = retry_prompt(short_text, OBJECT_SCHEMA, errors)
        assert short_text in prompt

    def test_prompt_with_nested_schema(self):
        errors = [ValidationError(message="missing items", path="$", schema_path="required")]
        prompt = retry_prompt("{}", NESTED_SCHEMA, errors)
        assert "items" in prompt

    def test_prompt_with_array_schema(self):
        schema = {"type": "array", "items": {"type": "integer"}}
        errors = [ValidationError(message="not array", path="$", schema_path="type")]
        prompt = retry_prompt("{}", schema, errors)
        assert "array" in prompt.lower()

    def test_prompt_numbered_errors(self):
        errors = [
            ValidationError(message="a", path="$.x", schema_path=""),
            ValidationError(message="b", path="$.y", schema_path=""),
        ]
        prompt = retry_prompt("{}", OBJECT_SCHEMA, errors)
        assert "1." in prompt
        assert "2." in prompt


# ═════════════════════════════════════════════════════════════════════
# Class 8 — TestExceptionHierarchy (10 cases)
# ═════════════════════════════════════════════════════════════════════


class TestExceptionHierarchy:
    """Tests for the exception classes and their attributes."""

    def test_base_exception(self):
        err = OutputGuardError("test")
        assert str(err) == "test"
        assert isinstance(err, Exception)

    def test_parse_error_inherits(self):
        assert issubclass(ParseError, OutputGuardError)

    def test_schema_error_inherits(self):
        assert issubclass(SchemaValidationError, OutputGuardError)

    def test_repair_error_inherits(self):
        assert issubclass(RepairError, OutputGuardError)

    def test_strategy_error_inherits(self):
        assert issubclass(StrategyError, OutputGuardError)

    def test_parse_error_attributes(self):
        err = ParseError("msg", original_text="raw", parse_error="detail")
        assert err.original_text == "raw"
        assert err.parse_error == "detail"
        assert str(err) == "msg"

    def test_schema_error_attributes(self):
        errs = [{"message": "bad"}]
        err = SchemaValidationError("msg", data={"a": 1}, errors=errs, schema={"type": "object"})
        assert err.data == {"a": 1}
        assert err.validation_errors == errs
        assert err.schema == {"type": "object"}

    def test_repair_error_attributes(self):
        err = RepairError("msg", strategies_tried=["a", "b"], original_text="raw")
        assert err.strategies_tried == ["a", "b"]
        assert err.original_text == "raw"

    def test_strategy_error_attributes(self):
        err = StrategyError("msg", strategy_name="fix_keys")
        assert err.strategy_name == "fix_keys"

    def test_exceptions_catchable_by_base(self):
        """All custom exceptions can be caught as OutputGuardError."""
        for exc_class in (ParseError, SchemaValidationError, RepairError, StrategyError):
            assert issubclass(exc_class, OutputGuardError)


# ═════════════════════════════════════════════════════════════════════
# Class 9 — TestCLIEdgeCases (15 cases)
# ═════════════════════════════════════════════════════════════════════


class TestCLIEdgeCases:
    """Tests for the Click CLI app edge cases."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_help(self):
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "validate" in result.output
        assert "repair" in result.output

    def test_validate_help(self):
        result = self.runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--schema" in result.output

    def test_repair_help(self):
        result = self.runner.invoke(cli, ["repair", "--help"])
        assert result.exit_code == 0

    def test_validate_missing_schema(self):
        result = self.runner.invoke(cli, ["validate", "-"], input='{"a": 1}')
        assert result.exit_code != 0  # Missing required -s

    def test_repair_empty_input(self):
        result = self.runner.invoke(cli, ["repair", "-"], input="")
        assert result.exit_code == 1

    def test_repair_valid_json(self):
        result = self.runner.invoke(cli, ["repair", "-"], input='{"a": 1}')
        assert result.exit_code == 0

    def test_repair_repairable_json(self):
        result = self.runner.invoke(cli, ["repair", "-"], input='```json\n{"a": 1}\n```')
        assert result.exit_code == 0

    def test_repair_json_format(self):
        result = self.runner.invoke(cli, ["repair", "-", "-f", "json"], input='{"a": 1}')
        assert result.exit_code == 0
        output = json.loads(result.output)
        assert "repaired" in output

    def test_strategies_command(self):
        result = self.runner.invoke(cli, ["strategies"])
        assert result.exit_code == 0
        assert "strip_fences" in result.output

    def test_version_command(self):
        result = self.runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "outputguard" in result.output

    def test_validate_with_schema_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as sf:
            json.dump(OBJECT_SCHEMA, sf)
            sf.flush()
            schema_path = sf.name
        try:
            result = self.runner.invoke(cli, ["validate", "-", "-s", schema_path], input='{"a": 1}')
            assert result.exit_code == 0
        finally:
            os.unlink(schema_path)

    def test_validate_invalid_with_schema_file(self):
        schema = {"type": "object", "required": ["x"]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as sf:
            json.dump(schema, sf)
            sf.flush()
            schema_path = sf.name
        try:
            result = self.runner.invoke(cli, ["validate", "-", "-s", schema_path], input='{"a": 1}')
            assert result.exit_code == 1
        finally:
            os.unlink(schema_path)

    def test_validate_repair_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as sf:
            json.dump(OBJECT_SCHEMA, sf)
            sf.flush()
            schema_path = sf.name
        try:
            result = self.runner.invoke(
                cli,
                ["validate", "-", "-s", schema_path, "--repair"],
                input='```json\n{"a": 1}\n```',
            )
            assert result.exit_code == 0
        finally:
            os.unlink(schema_path)

    def test_validate_json_format(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as sf:
            json.dump(OBJECT_SCHEMA, sf)
            sf.flush()
            schema_path = sf.name
        try:
            result = self.runner.invoke(
                cli,
                ["validate", "-", "-s", schema_path, "-f", "json"],
                input='{"a": 1}',
            )
            assert result.exit_code == 0
            output = json.loads(result.output)
            assert output["valid"] is True
        finally:
            os.unlink(schema_path)

    def test_retry_prompt_command(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as sf:
            json.dump(SIMPLE_SCHEMA, sf)
            sf.flush()
            schema_path = sf.name
        try:
            result = self.runner.invoke(
                cli,
                ["retry-prompt", "-", "-s", schema_path],
                input='{"wrong": true}',
            )
            assert result.exit_code == 0
            assert "name" in result.output
        finally:
            os.unlink(schema_path)


# ═════════════════════════════════════════════════════════════════════
# Class 10 — TestModelDataclasses (8 cases)
# ═════════════════════════════════════════════════════════════════════


class TestModelDataclasses:
    """Tests for the model dataclasses themselves."""

    def test_validation_error_fields(self):
        err = ValidationError(message="bad", path="$.x", schema_path="properties.x.type", value="v")
        assert err.message == "bad"
        assert err.path == "$.x"
        assert err.schema_path == "properties.x.type"
        assert err.value == "v"

    def test_validation_error_default_value(self):
        err = ValidationError(message="bad", path="$", schema_path="")
        assert err.value is None

    def test_validation_result_defaults(self):
        result = ValidationResult(valid=True)
        assert result.data is None
        assert result.errors == []
        assert result.repaired is False
        assert result.strategies_applied == []
        assert result.original_text == ""
        assert result.repaired_text == ""

    def test_repair_result_defaults(self):
        result = RepairResult(repaired=False, text="x")
        assert result.strategies_applied == []
        assert result.parse_error is None

    def test_strategy_application_unchanged_diff(self):
        sa = StrategyApplication(name="test", changed=False, input_text="a", output_text="a")
        assert sa.diff == ""

    def test_strategy_application_changed_diff(self):
        sa = StrategyApplication(name="test", changed=True, input_text="a\nb", output_text="a\nc")
        assert sa.diff != ""

    def test_repair_report_empty_steps(self):
        report = RepairReport(original_text="x", final_text="x", success=True)
        assert report.strategies_applied == []
        assert report.strategies_tried == []
        assert report.step_diffs() == ""

    def test_repair_report_no_parse_error_default(self):
        report = RepairReport(original_text="x", final_text="x", success=True)
        assert report.parse_error is None
