"""Test multi-strategy combinations and interactions.

Verifies that multiple repair strategies work correctly together,
that strategy ordering produces correct results, and that custom
strategy selection behaves as expected.
"""

import json

import pytest

from outputguard import OutputGuard, repair, validate_and_repair


class TestTwoStrategyCombinations:
    """Every meaningful pair of strategies applied together."""

    @pytest.mark.parametrize(
        "text",
        [
            # fences + commas
            pytest.param('```json\n{"a": 1,}\n```', id="fences+commas"),
            # fences + quotes
            pytest.param("```json\n{'a': 'b'}\n```", id="fences+quotes"),
            # fences + keys
            pytest.param('```json\n{a: 1}\n```', id="fences+keys"),
            # fences + booleans
            pytest.param('```json\n{"a": True}\n```', id="fences+booleans"),
            # fences + closers
            pytest.param('```json\n{"a": 1\n```', id="fences+closers"),
            # fences + values
            pytest.param('```json\n{"a": NaN}\n```', id="fences+values"),
            # fences + comments
            pytest.param('```json\n{"a": 1 // comment\n}\n```', id="fences+comments"),
            # fences + newlines
            pytest.param('```json\n{"a": "line1\nline2"}\n```', id="fences+newlines"),
            # fences + unicode
            pytest.param('```json\n{"a": "caf\\u00e9"}\n```', id="fences+unicode"),
            # fences + ellipsis
            pytest.param('```json\n{"a": [...]}\n```', id="fences+ellipsis"),
            # extract + quotes
            pytest.param("Here: {'a': 'b'} done", id="extract+quotes"),
            # extract + keys
            pytest.param('Output: {key: "val"} end', id="extract+keys"),
            # extract + booleans
            pytest.param('Result: {"a": True} end', id="extract+booleans"),
            # extract + commas
            pytest.param('Result: {"a": 1,} end', id="extract+commas"),
            # extract + values
            pytest.param('Output: {"x": NaN} end', id="extract+values"),
            # comments + commas
            pytest.param('{"a": 1, // x\n"b": 2,}', id="comments+commas"),
            # comments + keys
            pytest.param('{key: 1 // comment\n}', id="comments+keys"),
            # comments + quotes
            pytest.param("{'a': 1 // comment\n}", id="comments+quotes"),
            # comments + booleans
            pytest.param('{"a": True // flag\n}', id="comments+booleans"),
            # comments + values
            pytest.param('{"a": NaN // not a number\n}', id="comments+values"),
            # quotes + keys
            pytest.param("{key: 'val'}", id="quotes+keys"),
            # quotes + booleans
            pytest.param("{'a': True, 'b': False}", id="quotes+booleans"),
            # quotes + commas
            pytest.param("{'a': 1, 'b': 2,}", id="quotes+commas"),
            # keys + commas
            pytest.param('{key: "val", other: 2,}', id="keys+commas"),
            # keys + booleans
            pytest.param('{active: True, deleted: False}', id="keys+booleans"),
            # keys + values
            pytest.param('{score: NaN, count: Infinity}', id="keys+values"),
            # values + closers
            pytest.param('{"a": NaN, "b": [1, 2', id="values+closers"),
            # booleans + commas
            pytest.param('{"a": True, "b": False,}', id="booleans+commas"),
            # booleans + closers
            pytest.param('{"a": True, "b": [1', id="booleans+closers"),
            # commas + closers
            pytest.param('{"a": 1, "b": 2,', id="commas+closers"),
            # truncated + commas
            pytest.param('{"a": [1, 2,', id="truncated+commas"),
            # newlines + quotes
            pytest.param("{'msg': 'hello\\nworld'}", id="newlines+quotes"),
        ],
    )
    def test_two_strategy_combos(self, text):
        result = repair(text)
        assert result.repaired
        parsed = json.loads(result.text)
        assert isinstance(parsed, (dict, list))


class TestThreeStrategyCombinations:
    """Triple strategy combinations."""

    @pytest.mark.parametrize(
        "text",
        [
            # fences + quotes + commas
            pytest.param(
                "```json\n{'a': 1, 'b': 2,}\n```",
                id="fences+quotes+commas",
            ),
            # fences + keys + booleans
            pytest.param(
                '```json\n{active: True, name: "test"}\n```',
                id="fences+keys+booleans",
            ),
            # fences + comments + commas
            pytest.param(
                '```json\n{"a": 1, // note\n"b": 2,}\n```',
                id="fences+comments+commas",
            ),
            # fences + keys + commas
            pytest.param(
                '```json\n{key: "val", other: 2,}\n```',
                id="fences+keys+commas",
            ),
            # fences + quotes + booleans
            pytest.param(
                "```json\n{'active': True, 'name': 'test'}\n```",
                id="fences+quotes+booleans",
            ),
            # fences + values + commas
            pytest.param(
                '```json\n{"a": NaN, "b": 2,}\n```',
                id="fences+values+commas",
            ),
            # fences + keys + values
            pytest.param(
                '```json\n{score: NaN, active: True}\n```',
                id="fences+keys+values",
            ),
            # extract + quotes + keys
            pytest.param(
                "Result: {key: 'val', other: 'data'} end",
                id="extract+quotes+keys",
            ),
            # extract + keys + booleans
            pytest.param(
                'Output: {active: True, deleted: False} done',
                id="extract+keys+booleans",
            ),
            # extract + quotes + commas
            pytest.param(
                "Here: {'a': 1, 'b': 2,} done",
                id="extract+quotes+commas",
            ),
            # comments + quotes + commas
            pytest.param(
                "{'a': 1, // note\n'b': 2,}",
                id="comments+quotes+commas",
            ),
            # comments + keys + values
            pytest.param(
                '{key: NaN // not real\n}',
                id="comments+keys+values",
            ),
            # comments + keys + commas
            pytest.param(
                '{key: 1, // x\nother: 2,}',
                id="comments+keys+commas",
            ),
            # quotes + keys + commas
            pytest.param(
                "{key: 'val', other: 'data',}",
                id="quotes+keys+commas",
            ),
            # quotes + keys + booleans
            pytest.param(
                "{active: True, name: 'test'}",
                id="quotes+keys+booleans",
            ),
            # keys + booleans + commas
            pytest.param(
                '{active: True, deleted: False,}',
                id="keys+booleans+commas",
            ),
            # keys + values + commas
            pytest.param(
                '{score: NaN, count: Infinity,}',
                id="keys+values+commas",
            ),
            # fences + comments + keys
            pytest.param(
                '```json\n{key: 1 // comment\n}\n```',
                id="fences+comments+keys",
            ),
            # extract + comments + commas
            pytest.param(
                'Result: {"a": 1, // x\n"b": 2,} done',
                id="extract+comments+commas",
            ),
            # booleans + values + commas
            pytest.param(
                '{"active": True, "score": NaN,}',
                id="booleans+values+commas",
            ),
            # fences + quotes + keys + booleans (four!)
            pytest.param(
                "```json\n{active: True, name: 'test'}\n```",
                id="fences+quotes+keys+booleans",
            ),
            # fences + keys + commas + values (four!)
            pytest.param(
                '```json\n{score: NaN, count: Infinity,}\n```',
                id="fences+keys+commas+values",
            ),
            # fences + quotes + keys + booleans + commas (five!)
            pytest.param(
                "```json\n{name: 'Alice', active: True, age: 30,}\n```",
                id="fences+quotes+keys+booleans+commas",
            ),
        ],
    )
    def test_three_plus_strategy_combos(self, text):
        result = repair(text)
        assert result.repaired
        parsed = json.loads(result.text)
        assert isinstance(parsed, (dict, list))


class TestKitchenSink:
    """Inputs combining 4+ issues simultaneously."""

    @pytest.mark.parametrize(
        "text",
        [
            # fences + commentary + unquoted keys + single quotes + trailing comma + python bools
            pytest.param(
                "Sure!\n```json\n{name: 'Alice', age: 30, active: True,}\n```\nDone!",
                id="llm_full_mess",
            ),
            # commentary + JS object + NaN + comment + trailing comma
            pytest.param(
                "Result: {key: 'val', score: NaN, // note\n active: True,}",
                id="js_object_full",
            ),
            # fences + python dict + trailing comma + truncated
            pytest.param(
                "```json\n{'name': 'Bob', 'items': [1, 2,",
                id="fences+python+truncated",
            ),
            # fences + keys + values + booleans + commas
            pytest.param(
                '```json\n{name: "Test", val: NaN, active: True, count: 5,}\n```',
                id="fences+keys+vals+bools+commas",
            ),
            # extract + keys + quotes + booleans + values
            pytest.param(
                "Output: {name: 'Test', active: True, score: NaN} end",
                id="extract_everything",
            ),
            # deep nesting with multiple issues
            pytest.param(
                "```json\n{user: {name: 'Alice', prefs: {dark: True,}}}\n```",
                id="deep_nesting",
            ),
            # array with mixed issues
            pytest.param(
                "```json\n[{name: 'Alice', active: True,}, {name: 'Bob', active: False,}]\n```",
                id="array_mixed",
            ),
            # commentary wrapping fenced block with many issues
            pytest.param(
                "Here is the data:\n```json\n{items: [{id: 1, name: 'first',}, {id: 2, name: 'second',}],}\n```\nThat's all.",
                id="commentary_array_fenced",
            ),
            # keys + quotes + comments + commas
            pytest.param(
                "{name: 'Test', // user name\nage: 30, // years\nactive: True,}",
                id="keys_quotes_comments_commas",
            ),
            # fences + comments + keys + booleans + commas
            pytest.param(
                '```json\n{enabled: True, // flag\nname: "cfg",}\n```',
                id="fences_comments_keys_bools_commas",
            ),
            # extract with single quotes + booleans + trailing comma
            pytest.param(
                "The answer is: {'valid': True, 'count': 42,}. That's it.",
                id="extract_quotes_bools_commas",
            ),
            # deeply broken with many strategy needs
            pytest.param(
                "```json\n{users: [{name: 'Alice', active: True,}, {name: 'Bob', active: False,}], total: NaN,}\n```",
                id="max_strategies",
            ),
        ],
    )
    def test_kitchen_sink(self, text):
        result = repair(text)
        assert result.repaired
        data = json.loads(result.text)
        assert isinstance(data, (dict, list))


class TestStrategyOrdering:
    """Verify that strategy order matters and produces correct results."""

    def test_fences_before_extract(self):
        """If extract_json ran first, it might grab the wrong braces."""
        text = '```json\n{"a": 1}\n```\nSome {other} text'
        result = repair(text)
        assert json.loads(result.text) == {"a": 1}

    def test_comments_before_commas(self):
        """Comment removal must happen before comma fixing."""
        text = '{"a": 1, // comment\n}'
        result = repair(text)
        assert json.loads(result.text) == {"a": 1}

    def test_quotes_before_keys(self):
        """In {'key': 'val'}, quotes must be fixed before keys are detected."""
        text = "{'key': 'val'}"
        result = repair(text)
        assert json.loads(result.text) == {"key": "val"}

    def test_fences_then_quotes_then_commas(self):
        """Fences must come off first, then quotes, then commas."""
        text = "```json\n{'a': 1, 'b': 2,}\n```"
        result = repair(text)
        data = json.loads(result.text)
        assert data == {"a": 1, "b": 2}

    def test_fences_then_keys_then_booleans(self):
        """Fences first, then key quoting, then boolean fixing."""
        text = '```json\n{active: True, name: "test"}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["active"] is True
        assert data["name"] == "test"

    def test_comments_then_keys_then_values(self):
        """Comments removed, then keys quoted, then values fixed."""
        text = '{score: NaN // not real\n}'
        result = repair(text)
        data = json.loads(result.text)
        assert "score" in data

    def test_extract_then_quotes(self):
        """Extract JSON from commentary, then fix quotes."""
        text = "The result is {'answer': 42} and that's all."
        result = repair(text)
        data = json.loads(result.text)
        assert data["answer"] == 42

    def test_extract_then_keys_then_booleans(self):
        """Extract, quote keys, fix booleans."""
        text = "Output: {active: True, count: 5} end"
        result = repair(text)
        data = json.loads(result.text)
        assert data["active"] is True

    def test_fences_then_comments_then_commas(self):
        """Fences off, comments removed, trailing comma fixed."""
        text = '```json\n{"a": 1, // note\n"b": 2,}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data == {"a": 1, "b": 2}

    def test_fences_then_extract_priority(self):
        """Fences take priority over extract for code-fenced content."""
        text = '```json\n{"x": 1}\n```'
        result = repair(text)
        assert json.loads(result.text) == {"x": 1}

    def test_closers_after_all_content_fixes(self):
        """Closers should run last so content fixes happen first."""
        text = '{"a": True, "b": NaN, "c": [1, 2'
        result = repair(text)
        data = json.loads(result.text)
        assert "a" in data

    def test_booleans_independent_of_commas(self):
        """Both booleans and commas should be fixed regardless of order."""
        text = '{"a": True, "b": False, "c": None,}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["a"] is True
        assert data["b"] is False


class TestCustomStrategySelection:
    """Test OutputGuard with custom strategy subsets."""

    def test_subset_strategies_fixes_targeted(self):
        """With only strip_fences, fenced content is fixed."""
        guard = OutputGuard(strategies=["strip_fences"])
        result = guard.repair('```json\n{"a": 1}\n```')
        assert result.repaired
        assert json.loads(result.text) == {"a": 1}

    def test_subset_strategies_skips_others(self):
        """With only strip_fences, single-quote issues are NOT fixed."""
        guard = OutputGuard(strategies=["strip_fences"])
        result = guard.repair("{'a': 1}")
        assert not result.repaired

    def test_single_strategy_fix_commas(self):
        guard = OutputGuard(strategies=["fix_commas"])
        result = guard.repair('{"a": 1,}')
        assert result.repaired
        assert result.strategies_applied == ["fix_commas"]

    def test_single_strategy_fix_booleans(self):
        guard = OutputGuard(strategies=["fix_booleans"])
        result = guard.repair('{"a": True}')
        assert result.repaired
        assert result.strategies_applied == ["fix_booleans"]

    def test_single_strategy_fix_keys(self):
        guard = OutputGuard(strategies=["fix_keys"])
        result = guard.repair('{key: "val"}')
        assert result.repaired
        assert result.strategies_applied == ["fix_keys"]

    def test_single_strategy_fix_quotes(self):
        guard = OutputGuard(strategies=["fix_quotes"])
        result = guard.repair("{'a': 'b'}")
        assert result.repaired
        assert result.strategies_applied == ["fix_quotes"]

    def test_empty_strategy_list(self):
        guard = OutputGuard(strategies=[])
        result = guard.repair('```json\n{"a": 1}\n```')
        assert not result.repaired  # No strategies to apply

    def test_two_strategies_only(self):
        guard = OutputGuard(strategies=["strip_fences", "fix_commas"])
        result = guard.repair('```json\n{"a": 1,}\n```')
        assert result.repaired
        assert json.loads(result.text) == {"a": 1}

    def test_two_strategies_missing_needed(self):
        """When we have fences+commas but input also needs quotes, it should fail."""
        guard = OutputGuard(strategies=["strip_fences", "fix_commas"])
        result = guard.repair("```json\n{'a': 1,}\n```")
        # Without fix_quotes this cannot produce valid JSON
        assert not result.repaired

    def test_all_strategies_explicit(self):
        """Explicitly listing all strategies should work like default."""
        all_names = [
            "strip_fences", "extract_json", "remove_comments",
            "fix_commas", "fix_quotes", "fix_keys", "fix_values",
            "fix_booleans", "fix_truncated", "fix_ellipsis",
            "fix_unicode", "fix_inner_quotes", "fix_closers",
            "fix_newlines",
        ]
        guard = OutputGuard(strategies=all_names)
        text = "```json\n{name: 'Alice', active: True,}\n```"
        result = guard.repair(text)
        assert result.repaired
        data = json.loads(result.text)
        assert data["name"] == "Alice"


class TestRepairIdempotency:
    """Repairing already-repaired output should be a no-op."""

    @pytest.mark.parametrize(
        "broken_input",
        [
            pytest.param('```json\n{"a": 1}\n```', id="fenced"),
            pytest.param("{'key': 'value'}", id="single_quotes"),
            pytest.param('{key: "value", other: NaN,}', id="keys+values+commas"),
            pytest.param(
                "Sure!\n{name: 'Test', active: True}\nDone",
                id="commentary+keys+quotes+bools",
            ),
            pytest.param(
                '{"a": 1, // comment\n"b": 2,}',
                id="comments+commas",
            ),
            pytest.param('{"a": [1, 2', id="truncated_array"),
            pytest.param(
                "```json\n{name: 'Alice', age: 30, active: True,}\n```",
                id="fenced_kitchen_sink",
            ),
            pytest.param('{"a": True, "b": False}', id="python_bools"),
            pytest.param('{x: NaN}', id="keys+nan_value"),
            pytest.param('{"a": undefined}', id="undefined_value"),
            pytest.param(
                '```json\n{"items": [1, 2, 3,]}\n```',
                id="fenced_trailing_comma_array",
            ),
            pytest.param(
                "Output: {name: 'test'} done",
                id="extract+keys+quotes",
            ),
            pytest.param(
                '{key: "val", // comment\n}',
                id="keys+comments",
            ),
            pytest.param(
                '{active: True, deleted: False,}',
                id="keys+bools+commas",
            ),
            pytest.param(
                "```json\n{'enabled': True, 'name': 'cfg',}\n```",
                id="fenced+quotes+bools+commas",
            ),
        ],
    )
    def test_repair_then_repair_is_noop(self, broken_input):
        first = repair(broken_input)
        assert first.repaired
        second = repair(first.text)
        assert not second.repaired, (
            f"Second repair should be no-op but applied: {second.strategies_applied}"
        )
        assert second.text == first.text


class TestSchemaValidationWithRepair:
    """End-to-end: repair + schema validation."""

    schemas = {
        "user": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name", "age"],
        },
        "scores": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "number"}},
            },
            "required": ["values"],
        },
        "config": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "name": {"type": "string"},
            },
            "required": ["enabled", "name"],
        },
        "tags": {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tags"],
        },
    }

    @pytest.mark.parametrize(
        "text,schema_name",
        [
            pytest.param(
                "```json\n{'name': 'Alice', 'age': 30,}\n```",
                "user",
                id="fenced+quotes+commas->user",
            ),
            pytest.param(
                "{name: 'Bob', age: 25}",
                "user",
                id="keys+quotes->user",
            ),
            pytest.param(
                "{'values': [1.0, 2.5, 3.0,]}",
                "scores",
                id="quotes+commas->scores",
            ),
            pytest.param(
                "Sure: {'enabled': True, 'name': 'test'}\nDone",
                "config",
                id="extract+quotes+bools->config",
            ),
            pytest.param(
                '```json\n{name: "Test", age: 1, // a person\n}\n```',
                "user",
                id="fenced+keys+comments->user",
            ),
            pytest.param(
                '{enabled: True, name: "production",}',
                "config",
                id="keys+bools+commas->config",
            ),
            pytest.param(
                "Output: {name: 'Charlie', age: 35} end",
                "user",
                id="extract+keys+quotes->user",
            ),
            pytest.param(
                "{'tags': ['a', 'b', 'c',]}",
                "tags",
                id="quotes+commas->tags",
            ),
            pytest.param(
                '```json\n{"values": [1, 2, 3,]}\n```',
                "scores",
                id="fenced+commas->scores",
            ),
            pytest.param(
                "{enabled: True, name: 'dev', // config\n}",
                "config",
                id="keys+bools+quotes+comments->config",
            ),
            pytest.param(
                "```json\n{'tags': ['x', 'y',]}\n```",
                "tags",
                id="fenced+quotes+commas->tags",
            ),
        ],
    )
    def test_schema_repair_combos(self, text, schema_name):
        result = validate_and_repair(text, self.schemas[schema_name])
        assert result.valid, f"Expected valid but got errors: {result.errors}"
        assert result.repaired
        assert isinstance(result.data, (dict, list))
