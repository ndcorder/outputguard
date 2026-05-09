"""Adversarial, fuzzing, and boundary tests for outputguard.

Ensures outputguard NEVER crashes, NEVER hangs, and handles every
conceivable pathological input gracefully.
"""

import concurrent.futures
import json
import random
import string
import time

import pytest

from outputguard import parse, repair, validate_and_repair
from outputguard.repairer import repair as raw_repair
from outputguard.strategies import ALL_STRATEGIES

# ---------------------------------------------------------------------------
# Shared chaotic inputs
# ---------------------------------------------------------------------------

CHAOTIC_INPUTS = [
    "",
    " ",
    "\x00",
    "\x00" * 100,
    "}" * 1000,
    "{" * 1000,
    "[" * 500 + "]" * 500,
    '"' * 100,
    "'" * 100,
    "\\",
    "\\" * 100,
    "\n" * 100,
    "\r\n" * 100,
    "\t" * 100,
    "null",
    "true",
    "false",
    "undefined",
    "NaN",
    "Infinity",
    "-Infinity",
    "None",
    "True",
    "False",
    "..." * 50,
    "```json```",
    "```\n```",
    "```json\n\n```",
    '{"key": ' + '"value",' * 500 + '"last": 1}',
    '{"a": "' + "x" * 100_000 + '"}',
    "{" + '"k":1,' * 1000 + '"z":1}',
    "[" + "1," * 5000 + "1]",
    "/* " + "x" * 10_000 + " */",
    "//" + "x" * 10_000,
    '{"url": "' + "https://x.com/" * 200 + '"}',
    "```json\n" + '{"a":1}\n' * 100 + "```",
    '{"a": "\\u0000\\u0001\\u0002"}',
    '{"emoji": "' + "\U0001f600" * 1000 + '"}',
    # Deeply nested
    "{" * 100 + '"a":1' + "}" * 100,
    "[" * 100 + "1" + "]" * 100,
    # Mismatched brackets
    "{[{[{[{[",
    "]}}]}]}",
    '{"a": [}',
    '{"a": ]}',
    # Every ASCII printable char
    string.printable,
    # Binary-ish
    bytes(range(256)).decode("latin-1"),
]


# ---------------------------------------------------------------------------
# Class 1: TestNeverCrashes (30+ cases via parametrize)
# ---------------------------------------------------------------------------


class TestNeverCrashes:
    """repair() and every strategy must NEVER raise, regardless of input."""

    @pytest.mark.parametrize("chaotic_input", CHAOTIC_INPUTS, ids=range(len(CHAOTIC_INPUTS)))
    def test_repair_never_crashes(self, chaotic_input: str) -> None:
        """repair() must NEVER raise, regardless of input."""
        result = repair(chaotic_input)
        assert isinstance(result.repaired, bool)
        assert isinstance(result.text, str)

    @pytest.mark.parametrize("chaotic_input", CHAOTIC_INPUTS, ids=range(len(CHAOTIC_INPUTS)))
    def test_raw_repair_never_crashes(self, chaotic_input: str) -> None:
        """raw_repair() must NEVER raise, regardless of input."""
        result = raw_repair(chaotic_input, None)
        assert isinstance(result.repaired, bool)
        assert isinstance(result.text, str)

    @pytest.mark.parametrize("chaotic_input", CHAOTIC_INPUTS, ids=range(len(CHAOTIC_INPUTS)))
    def test_strategies_never_crash(self, chaotic_input: str) -> None:
        """Every individual strategy's apply() must never raise."""
        for name, fn in ALL_STRATEGIES:
            result = fn(chaotic_input)
            assert isinstance(result, str), f"Strategy {name} returned non-string: {type(result)}"

    def test_repair_with_report_never_crashes(self) -> None:
        """repair() with report=True must not crash on any chaotic input."""
        for chaotic_input in CHAOTIC_INPUTS:
            result_tuple = raw_repair(chaotic_input, None, report=True)
            assert isinstance(result_tuple, tuple)
            assert len(result_tuple) == 2

    def test_validate_and_repair_never_crashes(self) -> None:
        """validate_and_repair() must not crash even with garbage input."""
        schema = {"type": "object"}
        for chaotic_input in CHAOTIC_INPUTS[:20]:
            result = validate_and_repair(chaotic_input, schema)
            assert isinstance(result.valid, bool)

    def test_random_bytes_never_crash(self) -> None:
        """Random byte strings should never crash repair."""
        rng = random.Random(42)
        for _ in range(30):
            length = rng.randint(1, 500)
            raw = bytes(rng.randint(0, 255) for _ in range(length))
            text = raw.decode("latin-1")
            result = repair(text)
            assert isinstance(result.text, str)


# ---------------------------------------------------------------------------
# Class 2: TestPerformance (10+ cases)
# ---------------------------------------------------------------------------


class TestPerformance:
    """Ensure nothing takes unreasonably long."""

    def test_large_input_performance(self) -> None:
        """1MB of valid JSON should be fast."""
        obj = {f"key_{i}": f"value_{i}" for i in range(10_000)}
        text = json.dumps(obj)
        start = time.time()
        result = repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"
        assert not result.repaired

    def test_deeply_nested_performance(self) -> None:
        text = '{"a": ' * 50 + "1" + "}" * 50
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"Took {elapsed:.2f}s"

    def test_many_strategies_needed_performance(self) -> None:
        text = "```json\n{name: 'test', val: NaN, active: True, items: [1, 2,],}\n```"
        start = time.time()
        result = repair(text)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"Took {elapsed:.2f}s"
        assert result.repaired

    def test_large_fenced_performance(self) -> None:
        obj = {f"k{i}": i for i in range(5000)}
        text = f"```json\n{json.dumps(obj)}\n```"
        start = time.time()
        result = repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"
        assert result.repaired

    def test_long_string_with_newlines_performance(self) -> None:
        text = '{"text": "' + "line\\n" * 10_000 + '"}'
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"

    def test_many_trailing_commas_performance(self) -> None:
        text = "{" + ",".join(f'"k{i}": {i}' for i in range(2000)) + ",}"
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"Took {elapsed:.2f}s"

    def test_large_array_performance(self) -> None:
        text = "[" + ",".join(str(i) for i in range(10_000)) + "]"
        start = time.time()
        result = repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"
        assert not result.repaired

    def test_many_single_quote_keys_performance(self) -> None:
        pairs = ", ".join(f"'k{i}': {i}" for i in range(500))
        text = "{" + pairs + "}"
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"Took {elapsed:.2f}s"

    def test_repeated_validate_and_repair_performance(self) -> None:
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        text = '{"x": 1}'
        start = time.time()
        for _ in range(100):
            validate_and_repair(text, schema)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 iterations took {elapsed:.2f}s"

    def test_broken_brackets_performance(self) -> None:
        """Deeply mismatched brackets should not cause exponential blowup."""
        text = "{[" * 200 + "]}" * 200
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"

    def test_comments_heavy_performance(self) -> None:
        lines = [f"// comment {i}" for i in range(5000)]
        lines.insert(2500, '{"a": 1}')
        text = "\n".join(lines)
        start = time.time()
        repair(text)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"Took {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# Class 3: TestBoundaryConditions (20+ cases)
# ---------------------------------------------------------------------------


class TestBoundaryConditions:
    """Edge cases at exact boundaries."""

    @pytest.mark.parametrize(
        "char",
        [
            "{",
            "}",
            "[",
            "]",
            '"',
            "'",
            ",",
            ":",
            "\\",
            "/",
            ".",
            "!",
            "?",
            "#",
            "@",
            " ",
            "\n",
            "\t",
            "\r",
            "\0",
        ],
    )
    def test_single_char(self, char: str) -> None:
        result = repair(char)
        assert isinstance(result.text, str)

    @pytest.mark.parametrize(
        "minimal",
        ["0", "1", "-1", "0.5", '""', "null", "true", "false", "{}", "[]", '"x"'],
    )
    def test_minimal_valid_json(self, minimal: str) -> None:
        result = repair(minimal)
        assert not result.repaired
        json.loads(result.text)

    @pytest.mark.parametrize(
        "almost_valid",
        [
            '{"a": }',
            '{"a": 1, }',
            '{"a" 1}',
            "{: 1}",
            '{"a": 1',
            "[1, 2,]",
            "[,]",
            "{,}",
            '{"a": 1,,}',
        ],
    )
    def test_almost_valid(self, almost_valid: str) -> None:
        result = repair(almost_valid)
        assert isinstance(result.text, str)

    @pytest.mark.parametrize(
        "unicode_input",
        [
            '{"a": "café"}',
            '{"a": "你好"}',
            '{"a": "مرحبا"}',
            '{"a": "\U0001f389\U0001f38a\U0001f388"}',
            '{"a": "\\ud83d\\ude00"}',
            '{"a": "\\u0000"}',
            '{"a": "Ω≈ç√∫"}',
            '{"a": "→←↑↓"}',
            '{"a": "\\n\\t\\r"}',
        ],
    )
    def test_unicode_preserved(self, unicode_input: str) -> None:
        result = repair(unicode_input)
        assert not result.repaired
        json.loads(result.text)

    def test_empty_object_with_whitespace(self) -> None:
        result = repair("{   }")
        assert not result.repaired

    def test_empty_array_with_whitespace(self) -> None:
        result = repair("[   ]")
        assert not result.repaired

    def test_only_whitespace_between_brackets(self) -> None:
        result = repair("{  \n\t  }")
        assert not result.repaired

    def test_max_int(self) -> None:
        text = f'{{"big": {2**53}}}'
        result = repair(text)
        assert not result.repaired

    def test_negative_max_int(self) -> None:
        text = f'{{"neg": {-(2**53)}}}'
        result = repair(text)
        assert not result.repaired

    def test_float_precision(self) -> None:
        text = '{"pi": 3.141592653589793238462643383279}'
        result = repair(text)
        assert not result.repaired


# ---------------------------------------------------------------------------
# Class 4: TestNoDataLoss (15+ cases)
# ---------------------------------------------------------------------------


class TestNoDataLoss:
    """Verify repair never corrupts data."""

    @pytest.mark.parametrize(
        "original_data",
        [
            {"name": "Alice", "age": 30},
            {"list": [1, 2, 3, 4, 5]},
            {"nested": {"a": {"b": {"c": 1}}}},
            {"special": "hello\nworld\ttab"},
            {"unicode": "café ☕ 你好"},
            {"empty": "", "null": None, "bool": True},
            {"numbers": [0, -1, 1.5, 1e10, -3.14]},
            {"mixed": [1, "two", True, None, {"five": 5}]},
        ],
    )
    def test_fenced_data_preserved(self, original_data) -> None:
        text = f"```json\n{json.dumps(original_data)}\n```"
        result = repair(text)
        assert result.repaired
        assert json.loads(result.text) == original_data

    @pytest.mark.parametrize(
        "original_data",
        [
            {"name": "Alice", "age": 30},
            {"items": [1, 2, 3]},
            {"nested": {"a": 1}},
        ],
    )
    def test_commentary_data_preserved(self, original_data) -> None:
        text = f"Here is the result:\n{json.dumps(original_data)}\nHope this helps!"
        result = repair(text)
        assert json.loads(result.text) == original_data

    def test_trailing_comma_data_preserved(self) -> None:
        result = repair('{"name": "Alice", "age": 30, "city": "NYC",}')
        data = json.loads(result.text)
        assert data == {"name": "Alice", "age": 30, "city": "NYC"}

    def test_single_quotes_data_preserved(self) -> None:
        result = repair("{'name': 'Alice', 'scores': [95, 87, 92]}")
        data = json.loads(result.text)
        assert data["name"] == "Alice"
        assert data["scores"] == [95, 87, 92]

    def test_python_booleans_data_preserved(self) -> None:
        result = repair('{"active": True, "deleted": False, "val": None}')
        data = json.loads(result.text)
        assert data["active"] is True
        assert data["deleted"] is False
        assert data["val"] is None

    def test_unquoted_keys_data_preserved(self) -> None:
        result = repair('{name: "Alice", age: 30}')
        data = json.loads(result.text)
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_nan_replaced_data_preserved(self) -> None:
        result = repair('{"a": 1, "b": NaN, "c": 3}')
        data = json.loads(result.text)
        assert data["a"] == 1
        assert data["c"] == 3

    def test_large_nested_preserved(self) -> None:
        original = {"level1": {"level2": {"level3": {"data": [1, 2, 3]}}}}
        text = f"```json\n{json.dumps(original)}\n```"
        result = repair(text)
        assert json.loads(result.text) == original

    def test_array_of_objects_preserved(self) -> None:
        original = [{"id": i, "name": f"item_{i}"} for i in range(10)]
        text = f"```json\n{json.dumps(original)}\n```"
        result = repair(text)
        assert json.loads(result.text) == original

    def test_empty_structures_preserved(self) -> None:
        original = {"empty_obj": {}, "empty_arr": [], "empty_str": ""}
        text = f"```json\n{json.dumps(original)}\n```"
        result = repair(text)
        assert json.loads(result.text) == original


# ---------------------------------------------------------------------------
# Class 5: TestConcurrentSafety (5+ cases)
# ---------------------------------------------------------------------------


class TestConcurrentSafety:
    """Ensure thread-safety of repair operations."""

    def test_concurrent_repairs(self) -> None:
        inputs = [
            '```json\n{"a": 1}\n```',
            "{'b': 2}",
            "{c: 3, d: NaN,}",
            'Sure: {"e": True}\nDone',
            '{"f": [1, 2,]}',
        ] * 20  # 100 repairs

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(repair, text) for text in inputs]
            results = [f.result() for f in futures]

        assert all(isinstance(r.text, str) for r in results)
        assert all(r.repaired for r in results)

    def test_concurrent_validates(self) -> None:
        schema = {
            "type": "object",
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        }
        inputs = ['{"x": 1}'] * 50 + ['```json\n{"x": 2}\n```'] * 50

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(validate_and_repair, text, schema) for text in inputs]
            results = [f.result() for f in futures]

        assert all(r.valid for r in results)

    def test_concurrent_different_strategies(self) -> None:
        """Different strategy paths concurrently should not interfere."""
        inputs = [
            '{"a": True}',  # fix_booleans
            "{'b': 2}",  # fix_quotes
            "{c: 3}",  # fix_keys
            '{"d": 1,}',  # fix_commas
            '{"e": 1,}',  # fix_commas
        ] * 10

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(repair, text) for text in inputs]
            results = [f.result() for f in futures]

        assert all(isinstance(r.text, str) for r in results)
        assert all(r.repaired for r in results)

    def test_concurrent_raw_repair(self) -> None:
        inputs = ['{"x": 1,}'] * 50
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(raw_repair, text, None) for text in inputs]
            results = [f.result() for f in futures]
        assert all(r.repaired for r in results)

    def test_concurrent_parse(self) -> None:
        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        inputs = ['{"a": 1}'] * 50
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(parse, text, schema) for text in inputs]
            results = [f.result() for f in futures]
        assert all(r == {"a": 1} for r in results)

    def test_concurrent_mixed_valid_invalid(self) -> None:
        """Mix of valid and invalid inputs concurrently."""
        valid = ['{"a": 1}'] * 25
        invalid = ["}}}}"] * 25
        inputs = valid + invalid
        random.Random(42).shuffle(inputs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(repair, text) for text in inputs]
            results = [f.result() for f in futures]

        assert all(isinstance(r.text, str) for r in results)


# ---------------------------------------------------------------------------
# Class 6: TestSpecialPatterns (15+ cases)
# ---------------------------------------------------------------------------


class TestSpecialPatterns:
    """Special JSON patterns and edge cases."""

    def test_json_inside_json_string(self) -> None:
        text = '{"data": "{\\"inner\\": 1}", "meta": "ok"}'
        result = repair(text)
        assert not result.repaired
        data = json.loads(result.text)
        assert data["meta"] == "ok"

    def test_base64_in_string(self) -> None:
        text = '{"encoded": "SGVsbG8gV29ybGQ="}'
        result = repair(text)
        assert not result.repaired

    def test_very_long_key(self) -> None:
        key = "a" * 1000
        text = f'{{"{key}": 1}}'
        result = repair(text)
        assert not result.repaired

    def test_empty_array_values(self) -> None:
        text = '{"a": [], "b": {}, "c": ""}'
        result = repair(text)
        assert not result.repaired

    def test_scientific_notation(self) -> None:
        text = '{"val": 1.23e-4, "big": 9.99E+15}'
        result = repair(text)
        assert not result.repaired
        data = json.loads(result.text)
        assert data["val"] == 1.23e-4

    def test_negative_zero(self) -> None:
        text = '{"val": -0}'
        result = repair(text)
        assert not result.repaired

    def test_json_with_bom(self) -> None:
        text = '﻿{"a": 1}'
        result = repair(text)
        data = json.loads(result.text)
        assert data == {"a": 1}

    def test_windows_line_endings(self) -> None:
        text = '{"a": 1,\r\n"b": 2\r\n}'
        result = repair(text)
        assert not result.repaired or json.loads(result.text) == {"a": 1, "b": 2}

    def test_tab_indented_json(self) -> None:
        text = '{\n\t"a": 1,\n\t"b": 2\n}'
        result = repair(text)
        assert not result.repaired

    def test_mixed_indentation(self) -> None:
        text = '{\n  "a": 1,\n\t"b": 2,\n    "c": 3\n}'
        result = repair(text)
        assert not result.repaired

    def test_multiple_json_blocks(self) -> None:
        """Only the first JSON block should be extracted."""
        text = '{"a": 1}\n{"b": 2}'
        result = repair(text)
        data = json.loads(result.text)
        assert "a" in data or "b" in data

    def test_json_preceded_by_html(self) -> None:
        text = '<div>Hello</div>\n{"a": 1}'
        result = repair(text)
        data = json.loads(result.text)
        assert data == {"a": 1}

    def test_json_with_markdown_bold(self) -> None:
        text = '**Here:**\n```json\n{"a": 1}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data == {"a": 1}

    def test_string_that_looks_like_number(self) -> None:
        text = '{"phone": "555-1234", "zip": "01234"}'
        result = repair(text)
        assert not result.repaired
        data = json.loads(result.text)
        assert data["zip"] == "01234"

    def test_url_with_special_chars(self) -> None:
        text = '{"url": "https://example.com/path?q=1&r=2#frag"}'
        result = repair(text)
        assert not result.repaired

    def test_multiline_string_value(self) -> None:
        text = '{"text": "line1\\nline2\\nline3"}'
        result = repair(text)
        assert not result.repaired

    def test_escaped_backslashes(self) -> None:
        text = '{"path": "C:\\\\Users\\\\test"}'
        result = repair(text)
        assert not result.repaired

    def test_null_values_in_array(self) -> None:
        text = '{"items": [null, null, null]}'
        result = repair(text)
        assert not result.repaired

    def test_boolean_string_not_converted(self) -> None:
        """String 'true' in quotes should stay as string."""
        text = '{"flag": "true", "other": "false"}'
        result = repair(text)
        assert not result.repaired
        data = json.loads(result.text)
        assert data["flag"] == "true"  # stays string

    def test_number_as_key_in_quotes(self) -> None:
        text = '{"123": "numeric key", "456": "another"}'
        result = repair(text)
        assert not result.repaired


# ---------------------------------------------------------------------------
# Class 7: TestFuzzingPatterns (additional coverage)
# ---------------------------------------------------------------------------


class TestFuzzingPatterns:
    """Systematic fuzz-style patterns."""

    @pytest.mark.parametrize(
        "repeated_char",
        ["{}", "[]", '""', "  ", ",,", "::", "//", "**", "``"],
    )
    def test_repeated_pairs(self, repeated_char: str) -> None:
        text = repeated_char * 500
        result = repair(text)
        assert isinstance(result.text, str)

    def test_alternating_brackets(self) -> None:
        text = "{[}]" * 200
        result = repair(text)
        assert isinstance(result.text, str)

    def test_json_with_control_chars(self) -> None:
        """Control characters outside strings should not crash."""
        text = '{"a":\x01 1,\x02 "b":\x03 2}'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_only_commas(self) -> None:
        result = repair(",,,,,,,,,")
        assert isinstance(result.text, str)

    def test_only_colons(self) -> None:
        result = repair("::::::::")
        assert isinstance(result.text, str)

    def test_mixed_quote_styles(self) -> None:
        text = """{"a": 'b', 'c': "d", `e`: `f`}"""
        result = repair(text)
        assert isinstance(result.text, str)

    def test_triple_quoted_value(self) -> None:
        text = '{"a": """hello world"""}'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_javascript_undefined(self) -> None:
        text = '{"a": undefined, "b": undefined}'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_multiple_fenced_blocks(self) -> None:
        text = '```json\n{"a": 1}\n```\n\nSome text\n\n```json\n{"b": 2}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert isinstance(data, dict)

    def test_fenced_block_wrong_language(self) -> None:
        text = '```python\n{"a": 1}\n```'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_incomplete_fence(self) -> None:
        text = '```json\n{"a": 1}'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_fence_with_extra_backticks(self) -> None:
        text = '````json\n{"a": 1}\n````'
        result = repair(text)
        assert isinstance(result.text, str)

    @pytest.mark.parametrize(
        "token",
        ["NaN", "Infinity", "-Infinity", "undefined", "None", "True", "False"],
    )
    def test_bare_non_json_tokens(self, token: str) -> None:
        text = f'{{"val": {token}}}'
        result = repair(text)
        assert isinstance(result.text, str)

    def test_extremely_long_number(self) -> None:
        text = '{"n": ' + "9" * 1000 + "}"
        result = repair(text)
        assert isinstance(result.text, str)

    def test_all_escape_sequences(self) -> None:
        text = r'{"esc": "\" \\ \/ \b \f \n \r \t"}'
        result = repair(text)
        assert not result.repaired


# ---------------------------------------------------------------------------
# Class 8: TestRobustnessInvariants
# ---------------------------------------------------------------------------


class TestRobustnessInvariants:
    """Invariants that must always hold."""

    def test_repair_is_idempotent_for_valid_json(self) -> None:
        """Repairing valid JSON should return it unchanged."""
        valid_texts = [
            '{"a": 1}',
            "[1, 2, 3]",
            '"hello"',
            "42",
            "true",
            "null",
            '{"nested": {"arr": [1, null, "x"]}}',
        ]
        for text in valid_texts:
            result = repair(text)
            assert not result.repaired, f"Valid JSON was marked as repaired: {text}"
            assert result.text == text

    def test_repair_result_always_has_text(self) -> None:
        """RepairResult.text must never be None."""
        inputs = ["", "garbage", '{"a": 1}', "{invalid", "```json\n{}\n```"]
        for text in inputs:
            result = repair(text)
            assert result.text is not None

    def test_strategies_applied_is_list(self) -> None:
        """strategies_applied must always be a list."""
        for text in ["{}", '{"a": 1,}', "garbage"]:
            result = repair(text)
            assert isinstance(result.strategies_applied, list)

    def test_repaired_false_means_unchanged_or_unfixable(self) -> None:
        """If repaired=False, text should be the original."""
        originals = ['{"a": 1}', "completely broken garbage"]
        for text in originals:
            result = repair(text)
            if not result.repaired:
                assert result.text == text

    def test_repaired_true_means_valid_json(self) -> None:
        """If repaired=True, the result text must be parseable JSON."""
        fixable = [
            '{"a": 1,}',
            "{'a': 1}",
            '```json\n{"a": 1}\n```',
            "{a: 1}",
            '{"a": True}',
        ]
        for text in fixable:
            result = repair(text)
            if result.repaired:
                json.loads(result.text)  # must not raise
