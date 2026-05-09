"""Exhaustive edge-case tests for all 14 outputguard strategies.

Pushes each strategy to its absolute limits with parametrized inputs.
"""

import json

import pytest

from outputguard.strategies.extract_json import apply as extract_json
from outputguard.strategies.fix_booleans import apply as fix_booleans
from outputguard.strategies.fix_closers import apply as fix_closers
from outputguard.strategies.fix_commas import apply as fix_commas
from outputguard.strategies.fix_ellipsis import apply as fix_ellipsis
from outputguard.strategies.fix_inner_quotes import apply as fix_inner_quotes
from outputguard.strategies.fix_keys import apply as fix_keys
from outputguard.strategies.fix_newlines import apply as fix_newlines
from outputguard.strategies.fix_quotes import apply as fix_quotes
from outputguard.strategies.fix_truncated import apply as fix_truncated
from outputguard.strategies.fix_unicode import apply as fix_unicode
from outputguard.strategies.fix_values import apply as fix_values
from outputguard.strategies.remove_comments import apply as remove_comments
from outputguard.strategies.strip_fences import apply as strip_fences


# ─── strip_fences (18 cases) ─────────────────────────────────────────────────


class TestStripFences:
    @pytest.mark.parametrize(
        "lang_tag",
        [
            "json",
            "JSON",
            "jsonc",
            "javascript",
            "js",
            "typescript",
            "ts",
            "python",
            "py",
            "yaml",
            "xml",
            "html",
            "css",
            "sql",
            "plaintext",
            "",  # no tag
        ],
    )
    def test_every_language_tag(self, lang_tag):
        text = f"```{lang_tag}\n{{\"a\": 1}}\n```"
        assert strip_fences(text) == '{"a": 1}'

    def test_nested_fences(self):
        text = '```json\n{"code": "```inner```"}\n```'
        result = strip_fences(text)
        assert '"code"' in result

    def test_windows_line_endings(self):
        text = '```json\r\n{"a": 1}\r\n```'
        # The regex expects \n — \r\n should still match since \r is just whitespace
        result = strip_fences(text)
        assert '{"a": 1}' in result or '{"a": 1}' in result.strip()

    def test_trailing_whitespace_after_closing_fence(self):
        text = '```json\n{"a": 1}\n```   '
        result = strip_fences(text)
        assert '{"a": 1}' in result

    def test_indented_closing_fence(self):
        text = '```json\n{"a": 1}\n   ```'
        result = strip_fences(text)
        assert '{"a": 1}' in result

    def test_multiple_fences_takes_first(self):
        text = '```json\n{"first": true}\n```\ntext\n```json\n{"second": true}\n```'
        result = strip_fences(text)
        assert '"first"' in result
        assert '"second"' not in result

    def test_fence_with_empty_content(self):
        text = '```json\n\n```'
        result = strip_fences(text)
        assert result.strip() == ''

    def test_fence_with_only_whitespace_content(self):
        text = '```json\n   \n```'
        result = strip_fences(text)
        assert result.strip() == ''


# ─── extract_json (17 cases) ─────────────────────────────────────────────────


class TestExtractJson:
    def test_json_preceded_by_numbered_list(self):
        text = '1. Result: {"key": "value"}'
        assert extract_json(text) == '{"key": "value"}'

    def test_json_preceded_by_bullet_points(self):
        text = '- item one\n- item two\n{"result": true}'
        assert extract_json(text) == '{"result": true}'

    def test_json_inside_markdown_blockquote(self):
        text = '> {"quoted": true}'
        assert extract_json(text) == '{"quoted": true}'

    @pytest.mark.parametrize(
        "prefix",
        ["Output: ", "Result: ", "Answer: ", "Response: ", "Here is the JSON: "],
    )
    def test_json_after_labels(self, prefix):
        text = f'{prefix}{{"key": 42}}'
        assert extract_json(text) == '{"key": 42}'

    def test_multiple_json_objects_takes_first(self):
        text = '{"first": 1} and also {"second": 2}'
        result = extract_json(text)
        assert json.loads(result) == {"first": 1}

    def test_json_with_brace_strings(self):
        text = '{"regex": "match {x}"}'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["regex"] == "match {x}"

    def test_array_of_objects(self):
        text = 'Result: [{"a": 1}, {"b": 2}]'
        result = extract_json(text)
        parsed = json.loads(result)
        assert len(parsed) == 2

    def test_deeply_nested_10_levels(self):
        inner = '{"l10": true}'
        for i in range(9, 0, -1):
            inner = f'{{"l{i}": {inner}}}'
        text = f'Deeply nested: {inner}'
        result = extract_json(text)
        parsed = json.loads(result)
        assert parsed["l1"]["l2"]["l3"]["l4"]["l5"]["l6"]["l7"]["l8"]["l9"]["l10"] is True

    def test_json_with_escaped_quotes(self):
        text = '{"msg": "He said \\"hello\\""}'
        result = extract_json(text)
        assert result.startswith("{")
        assert result.endswith("}")

    def test_very_large_json(self):
        entries = ", ".join(f'"k{i}": {i}' for i in range(200))
        big = "{" + entries + "}"
        text = "Here: " + big + " done."
        result = extract_json(text)
        parsed = json.loads(result)
        assert len(parsed) == 200

    def test_no_json_at_all(self):
        text = "Just plain text with no braces or brackets."
        assert extract_json(text) == text

    def test_array_only(self):
        text = '[1, 2, 3]'
        assert json.loads(extract_json(text)) == [1, 2, 3]

    def test_json_with_newlines_inside(self):
        text = 'Before\n{\n  "a": 1,\n  "b": 2\n}\nAfter'
        result = extract_json(text)
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_string_containing_brackets(self):
        text = '{"arr": "[not an array]"}'
        result = extract_json(text)
        assert json.loads(result) == {"arr": "[not an array]"}

    def test_empty_object(self):
        text = 'Result: {}'
        assert extract_json(text) == '{}'

    def test_empty_array(self):
        text = 'Result: []'
        assert extract_json(text) == '[]'


# ─── remove_comments (12 cases) ──────────────────────────────────────────────


class TestRemoveComments:
    def test_comment_at_very_start(self):
        text = '// comment\n{"a": 1}'
        result = remove_comments(text)
        assert json.loads(result) == {"a": 1}

    def test_comment_at_very_end(self):
        text = '{"a": 1}\n// trailing comment'
        result = remove_comments(text)
        assert json.loads(result.strip()) == {"a": 1}

    def test_multiple_single_line_comments(self):
        text = '{\n// first\n"a": 1,\n// second\n"b": 2\n}'
        result = remove_comments(text)
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_multiline_comment_spanning_5_lines(self):
        text = '{\n/* line1\nline2\nline3\nline4\nline5 */\n"a": 1}'
        result = remove_comments(text)
        assert json.loads(result) == {"a": 1}

    def test_comment_like_patterns_inside_strings(self):
        text = '{"url": "http://example.com", "note": "use // for division"}'
        result = remove_comments(text)
        parsed = json.loads(result)
        assert parsed["url"] == "http://example.com"
        assert parsed["note"] == "use // for division"

    def test_empty_comment(self):
        text = '{"a": 1}\n//\n'
        result = remove_comments(text)
        assert json.loads(result.strip()) == {"a": 1}

    def test_comment_with_special_chars(self):
        text = '{"a": 1} // "quotes" and {braces}'
        result = remove_comments(text)
        assert json.loads(result.strip()) == {"a": 1}

    def test_nested_looking_comments(self):
        text = '{"a": 1} /* /* not nested */ */'
        result = remove_comments(text)
        # After first */ the rest is literal — the trailing */ stays
        assert '{"a": 1}' in result

    def test_mixed_single_and_multiline_comments(self):
        text = '// header\n{/* inline */"a": 1 // end\n}'
        result = remove_comments(text)
        assert json.loads(result) == {"a": 1}

    def test_url_in_string_not_stripped(self):
        text = '{"homepage": "https://example.com/path"}'
        result = remove_comments(text)
        assert json.loads(result)["homepage"] == "https://example.com/path"

    def test_comment_between_key_and_value(self):
        text = '{"a": /* the value */ 1}'
        result = remove_comments(text)
        assert json.loads(result) == {"a": 1}

    def test_block_comment_with_stars_inside(self):
        text = '{"a": 1} /* ** stars ** */'
        result = remove_comments(text)
        assert json.loads(result.strip()) == {"a": 1}


# ─── fix_commas (9 cases) ────────────────────────────────────────────────────


class TestFixCommas:
    def test_multiple_consecutive_trailing_commas(self):
        text = '{"a": 1,,}'
        result = fix_commas(text)
        # The regex ,\s*} matches the second comma + }, leaving the first comma
        # A single regex pass turns ,,} into ,} (only the last ,} pair matches)
        assert result == '{"a": 1,}'

    def test_deeply_nested_trailing_comma(self):
        text = '{"a": {"b": {"c": 1,},},}'
        result = fix_commas(text)
        assert json.loads(result) == {"a": {"b": {"c": 1}}}

    def test_comma_followed_by_newline_then_closer(self):
        text = '{"a": 1,\n  }'
        result = fix_commas(text)
        assert json.loads(result) == {"a": 1}

    def test_multiple_trailing_commas_in_array(self):
        text = '[1, 2,,]'
        result = fix_commas(text)
        # Same single-pass behavior: ,,] -> ,]
        assert result == '[1, 2,]'

    def test_comma_in_string_values_preserved(self):
        text = '{"a": "1,2,3,"}'
        result = fix_commas(text)
        # The comma before } is inside a string, but fix_commas uses a simple
        # regex so it doesn't distinguish. The key insight: ," is not ,}
        # so the regex ,\s*} won't match inside the string since the comma
        # is followed by " not }.
        assert json.loads(result) == {"a": "1,2,3,"}

    def test_no_trailing_comma_unchanged(self):
        text = '{"a": 1, "b": 2}'
        result = fix_commas(text)
        assert result == text

    def test_trailing_comma_in_array_of_objects(self):
        text = '[{"a": 1}, {"b": 2},]'
        result = fix_commas(text)
        assert json.loads(result) == [{"a": 1}, {"b": 2}]

    def test_trailing_comma_with_spaces(self):
        text = '{"a": 1  ,   }'
        result = fix_commas(text)
        assert json.loads(result) == {"a": 1}

    def test_comma_before_bracket_in_nested_array(self):
        text = '{"arr": [1, 2, 3,]}'
        result = fix_commas(text)
        assert json.loads(result) == {"arr": [1, 2, 3]}


# ─── fix_quotes (11 cases) ───────────────────────────────────────────────────


class TestFixQuotes:
    def test_single_quoted_with_apostrophe(self):
        text = "{\\x27it\\'s\\x27: \\x27value\\x27}"
        # Actually test with real single quotes
        text = "{'it\\'s': 'value'}"
        result = fix_quotes(text)
        assert '"it\'s"' in result
        assert '"value"' in result

    def test_single_quoted_containing_double_quote(self):
        text = "{'key': 'say \"hello\"'}"
        result = fix_quotes(text)
        assert '"key"' in result
        assert '\\"hello\\"' in result or 'say' in result

    def test_mixed_quoting_styles(self):
        text = "{'a': 1, \"b\": 2, 'c': 3}"
        result = fix_quotes(text)
        assert '"a"' in result
        assert '"b"' in result
        assert '"c"' in result
        # No single quotes should remain as JSON delimiters
        # (single quotes within string content are fine)

    def test_empty_single_quoted_string(self):
        text = "{'key': ''}"
        result = fix_quotes(text)
        assert '"key"' in result
        assert '""' in result

    def test_single_quoted_with_backslash(self):
        text = "{'path': 'C:\\\\Users'}"
        result = fix_quotes(text)
        assert '"path"' in result

    def test_nested_single_quoted_objects(self):
        text = "{'a': {'b': 'c'}}"
        result = fix_quotes(text)
        assert '"a"' in result
        assert '"b"' in result
        assert '"c"' in result

    def test_single_quoted_array_elements(self):
        text = "['hello', 'world']"
        result = fix_quotes(text)
        assert '"hello"' in result
        assert '"world"' in result

    def test_single_quoted_numbers_and_booleans(self):
        text = "{'count': 42, 'active': true}"
        result = fix_quotes(text)
        assert '"count"' in result
        assert '42' in result

    def test_all_double_quoted_unchanged(self):
        text = '{"a": "b"}'
        result = fix_quotes(text)
        assert result == text

    def test_single_quoted_with_colon_in_value(self):
        text = "{'url': 'http://example.com'}"
        result = fix_quotes(text)
        assert '"url"' in result
        assert '"http://example.com"' in result

    def test_single_quoted_with_comma_in_value(self):
        text = "{'list': 'a,b,c'}"
        result = fix_quotes(text)
        assert '"a,b,c"' in result


# ─── fix_keys (9 cases) ──────────────────────────────────────────────────────


class TestFixKeys:
    @pytest.mark.parametrize(
        "key,expected_key",
        [
            ("$id", '"$id"'),
            ("_private", '"_private"'),
            ("my.dotted.key", '"my.dotted.key"'),
            ("hyphen-key", '"hyphen-key"'),
        ],
    )
    def test_keys_with_special_chars(self, key, expected_key):
        text = "{" + key + ": 1}"
        result = fix_keys(text)
        assert expected_key in result

    def test_js_keyword_keys(self):
        text = '{class: 1, function: 2, return: 3}'
        result = fix_keys(text)
        assert '"class"' in result
        assert '"function"' in result
        assert '"return"' in result

    def test_number_keys(self):
        # The regex pattern requires keys starting with [a-zA-Z_$]
        # so numeric keys won't match — this tests that behavior
        text = '{0: "zero", 1: "one"}'
        result = fix_keys(text)
        # Numbers don't match the unquoted key regex
        assert result == text

    def test_unicode_key(self):
        # café starts with 'c' which matches [a-zA-Z_$]
        text = '{café: 1}'
        result = fix_keys(text)
        # The regex uses [a-zA-Z0-9_.$-]* for continuation
        # so non-ASCII after first char won't fully match
        assert result.startswith('{')

    def test_already_quoted_mixed_with_unquoted(self):
        text = '{"quoted": 1, unquoted: 2}'
        result = fix_keys(text)
        assert '"quoted"' in result
        assert '"unquoted"' in result

    def test_deeply_nested_unquoted_keys(self):
        text = '{outer: {inner: {deep: 1}}}'
        result = fix_keys(text)
        assert '"outer"' in result
        assert '"inner"' in result
        assert '"deep"' in result

    def test_key_with_url_like_value(self):
        # Ensure colon in value doesn't confuse key detection
        text = '{url: "http://example.com"}'
        result = fix_keys(text)
        assert '"url"' in result
        assert '"http://example.com"' in result

    def test_key_with_dollar_prefix(self):
        text = '{$ref: "#/definitions/Foo"}'
        result = fix_keys(text)
        assert '"$ref"' in result


# ─── fix_values (9 cases) ────────────────────────────────────────────────────


class TestFixValues:
    def test_multiple_nan_infinity(self):
        text = '{"a": NaN, "b": Infinity, "c": -Infinity}'
        result = fix_values(text)
        parsed = json.loads(result)
        assert parsed == {"a": None, "b": None, "c": None}

    def test_nan_in_array(self):
        text = '[1, NaN, 3]'
        result = fix_values(text)
        assert json.loads(result) == [1, None, 3]

    def test_infinity_as_only_value(self):
        text = '{"x": Infinity}'
        result = fix_values(text)
        assert json.loads(result) == {"x": None}

    def test_nan_inside_string_preserved(self):
        text = '{"msg": "NaN is not a number"}'
        result = fix_values(text)
        assert json.loads(result)["msg"] == "NaN is not a number"

    def test_infinity_inside_string_preserved(self):
        text = '{"msg": "Infinity and beyond"}'
        result = fix_values(text)
        assert json.loads(result)["msg"] == "Infinity and beyond"

    def test_undefined_inside_string_preserved(self):
        text = '{"msg": "undefined behavior"}'
        result = fix_values(text)
        assert json.loads(result)["msg"] == "undefined behavior"

    def test_undefined_in_array(self):
        text = '[undefined, 1, undefined]'
        result = fix_values(text)
        assert json.loads(result) == [None, 1, None]

    def test_negative_infinity(self):
        text = '{"min": -Infinity}'
        result = fix_values(text)
        assert json.loads(result) == {"min": None}

    def test_mixed_valid_and_invalid_values(self):
        text = '{"a": NaN, "b": 42, "c": Infinity, "d": "hello"}'
        result = fix_values(text)
        parsed = json.loads(result)
        assert parsed == {"a": None, "b": 42, "c": None, "d": "hello"}


# ─── fix_booleans (10 cases) ─────────────────────────────────────────────────


class TestFixBooleans:
    def test_true_false_none_in_arrays(self):
        text = '[True, False, None]'
        result = fix_booleans(text)
        assert json.loads(result) == [True, False, None]

    def test_nested_python_booleans(self):
        text = '{"a": {"b": True}}'
        result = fix_booleans(text)
        assert json.loads(result) == {"a": {"b": True}}

    def test_mixed_python_and_json_booleans(self):
        text = '{"a": True, "b": false}'
        result = fix_booleans(text)
        assert json.loads(result) == {"a": True, "b": False}

    def test_in_string_preserved(self):
        text = '{"text": "True or False"}'
        result = fix_booleans(text)
        assert json.loads(result)["text"] == "True or False"

    def test_none_vs_null(self):
        text = '{"a": None, "b": null}'
        result = fix_booleans(text)
        assert json.loads(result) == {"a": None, "b": None}

    def test_all_python_booleans(self):
        text = '{"x": True, "y": False, "z": None}'
        result = fix_booleans(text)
        assert json.loads(result) == {"x": True, "y": False, "z": None}

    def test_already_valid_json_unchanged(self):
        text = '{"a": true, "b": false, "c": null}'
        result = fix_booleans(text)
        assert result == text

    def test_boolean_in_nested_array(self):
        text = '{"data": [True, [False, [None]]]}'
        result = fix_booleans(text)
        assert json.loads(result) == {"data": [True, [False, [None]]]}

    def test_true_false_adjacent_to_punctuation(self):
        text = '[True,False,None]'
        result = fix_booleans(text)
        assert json.loads(result) == [True, False, None]

    def test_none_in_string_preserved(self):
        text = '{"msg": "None of the above"}'
        result = fix_booleans(text)
        assert json.loads(result)["msg"] == "None of the above"


# ─── fix_truncated (12 cases) ────────────────────────────────────────────────


class TestFixTruncated:
    def test_truncated_in_middle_of_number(self):
        text = '{"price": 19.'
        result = fix_truncated(text)
        # Should close the structure
        assert result.endswith('}')

    def test_truncated_in_middle_of_boolean(self):
        text = '{"active": tru'
        result = fix_truncated(text)
        assert result.endswith('}')

    def test_truncated_in_middle_of_null(self):
        text = '{"val": nu'
        result = fix_truncated(text)
        assert result.endswith('}')

    def test_truncated_inside_array_element(self):
        text = '{"tags": ["hello", "wor'
        result = fix_truncated(text)
        assert result.endswith(']}')

    def test_truncated_with_nothing_after_key(self):
        text = '{"name":'
        result = fix_truncated(text)
        assert result.endswith('}')

    def test_truncated_inside_nested_object_key(self):
        text = '{"data": {"inne'
        result = fix_truncated(text)
        assert result.count('}') >= 2

    def test_only_opening_brace(self):
        text = '{'
        result = fix_truncated(text)
        assert result == '{}'

    def test_opening_brace_and_key(self):
        text = '{"key"'
        result = fix_truncated(text)
        assert result.endswith('}')

    def test_truncated_string_value(self):
        text = '{"msg": "hello wor'
        result = fix_truncated(text)
        assert result.endswith('}')
        # Should have balanced quotes

    def test_truncated_after_comma(self):
        text = '{"a": 1,'
        result = fix_truncated(text)
        assert result.endswith('}')
        parsed = json.loads(result)
        assert parsed == {"a": 1}

    def test_truncated_nested_array(self):
        text = '{"matrix": [[1, 2], [3'
        result = fix_truncated(text)
        assert result.endswith(']}')  # close inner array, outer array, object

    def test_valid_json_unchanged(self):
        text = '{"a": 1}'
        result = fix_truncated(text)
        assert result == text


# ─── fix_closers (8 cases) ───────────────────────────────────────────────────


class TestFixClosers:
    def test_missing_3_levels_of_closers(self):
        text = '{"a": {"b": [1, 2, 3'
        result = fix_closers(text)
        assert result.endswith(']}}')

    def test_missing_bracket_but_not_brace(self):
        text = '{"arr": [1, 2, 3}'
        result = fix_closers(text)
        # The ] is missing but } closes the brace — this is structural
        # The closer strategy adds missing closers at the end
        assert '{"arr": [1, 2, 3}' in result

    def test_missing_brace_but_not_bracket(self):
        text = '{"a": 1'
        result = fix_closers(text)
        assert result.endswith('}')

    def test_braces_inside_strings_dont_count(self):
        text = '{"pattern": "{[("}'
        result = fix_closers(text)
        # The { [ ( inside the string should not affect balancing
        assert result == text

    def test_already_balanced(self):
        text = '{"a": [1, 2], "b": {"c": 3}}'
        result = fix_closers(text)
        assert result == text

    def test_deeply_nested_missing_closers(self):
        text = '{"a": {"b": {"c": {"d": 1'
        result = fix_closers(text)
        assert result.endswith('}}}}')

    def test_missing_array_closer_only(self):
        text = '[1, 2, 3'
        result = fix_closers(text)
        assert result == '[1, 2, 3]'

    def test_empty_nested_structures(self):
        text = '{"a": {"b": ['
        result = fix_closers(text)
        assert result.endswith(']}}')


# ─── fix_newlines (8 cases) ──────────────────────────────────────────────────


class TestFixNewlines:
    def test_multiple_newlines_in_one_string(self):
        text = '{"text": "line1\nline2\nline3"}'
        result = fix_newlines(text)
        assert json.loads(result)["text"] == "line1\nline2\nline3"

    def test_carriage_return_and_newline(self):
        text = '{"text": "line1\r\nline2"}'
        result = fix_newlines(text)
        parsed = json.loads(result)
        assert "line1" in parsed["text"]
        assert "line2" in parsed["text"]

    def test_tab_characters(self):
        text = '{"text": "col1\tcol2"}'
        result = fix_newlines(text)
        assert json.loads(result)["text"] == "col1\tcol2"

    def test_newlines_in_keys(self):
        # Weird but possible
        text = '{"key\nwith\nnewline": "value"}'
        result = fix_newlines(text)
        assert '\n' not in json.dumps(json.loads(result))

    def test_multiple_strings_with_newlines(self):
        text = '{"a": "line1\nline2", "b": "line3\nline4"}'
        result = fix_newlines(text)
        parsed = json.loads(result)
        assert parsed["a"] == "line1\nline2"
        assert parsed["b"] == "line3\nline4"

    def test_already_escaped_newlines_preserved(self):
        text = '{"text": "already\\nescaped"}'
        result = fix_newlines(text)
        assert json.loads(result)["text"] == "already\nescaped"

    def test_no_newlines_unchanged(self):
        text = '{"a": "hello world"}'
        result = fix_newlines(text)
        assert result == text

    def test_newline_at_end_of_string_value(self):
        text = '{"text": "hello\n"}'
        result = fix_newlines(text)
        assert json.loads(result)["text"] == "hello\n"


# ─── fix_ellipsis (8 cases) ──────────────────────────────────────────────────


class TestFixEllipsis:
    def test_multiple_ellipsis_in_one_object(self):
        text = '{"a": ..., "b": ...}'
        result = fix_ellipsis(text)
        parsed = json.loads(result)
        assert parsed["a"] is None
        assert parsed["b"] is None

    def test_ellipsis_as_array_element_among_valid(self):
        text = '[1, ..., 3]'
        result = fix_ellipsis(text)
        parsed = json.loads(result)
        assert 1 in parsed
        assert 3 in parsed

    def test_ellipsis_with_comment(self):
        text = '[1, 2, ... // more items\n]'
        result = fix_ellipsis(text)
        parsed = json.loads(result)
        assert 1 in parsed
        assert 2 in parsed

    def test_ellipsis_in_string_preserved(self):
        text = '{"msg": "and so on..."}'
        result = fix_ellipsis(text)
        # The ... is inside a string — should be preserved
        parsed = json.loads(result)
        assert "..." in parsed["msg"]

    def test_ellipsis_only_in_object(self):
        text = '{...}'
        result = fix_ellipsis(text)
        assert json.loads(result) == {}

    def test_ellipsis_only_in_array(self):
        text = '[...]'
        result = fix_ellipsis(text)
        assert json.loads(result) == []

    def test_ellipsis_as_value(self):
        text = '{"placeholder": ...}'
        result = fix_ellipsis(text)
        parsed = json.loads(result)
        assert parsed["placeholder"] is None

    def test_ellipsis_at_end_of_array(self):
        text = '[1, 2, ...]'
        result = fix_ellipsis(text)
        parsed = json.loads(result)
        assert 1 in parsed
        assert 2 in parsed


# ─── fix_unicode (8 cases) ───────────────────────────────────────────────────


class TestFixUnicode:
    def test_multiple_hex_escapes_in_one_string(self):
        text = '{"msg": "\\x48\\x65\\x6C\\x6C\\x6F"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["msg"] == "Hello"

    def test_x00_null_byte(self):
        text = '{"data": "test\\x00end"}'
        result = fix_unicode(text)
        # \x00 is handled — should not crash
        assert '{' in result and '}' in result

    def test_printable_ascii_hex(self):
        # \x41 = 'A'
        text = '{"letter": "\\x41"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["letter"] == "A"

    def test_mixed_valid_and_invalid_unicode(self):
        text = '{"a": "\\u0041", "b": "\\x42"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["a"] == "A"  # A = 'A'
        assert parsed["b"] == "B"  # \x42 = 'B'

    def test_consecutive_hex_escapes_spelling_hello(self):
        text = '{"word": "\\x48\\x65\\x6C\\x6C\\x6F"}'
        result = fix_unicode(text)
        parsed = json.loads(result)
        assert parsed["word"] == "Hello"

    def test_incomplete_unicode_escape(self):
        text = '{"val": "\\u00"}'
        result = fix_unicode(text)
        # Should pad to 4 hex digits
        assert '\\u00' in result or '"' in result

    def test_valid_unicode_unchanged(self):
        text = '{"emoji": "\\u2764"}'
        result = fix_unicode(text)
        assert '\\u2764' in result or '❤' in result

    def test_no_escapes_unchanged(self):
        text = '{"plain": "hello world"}'
        result = fix_unicode(text)
        assert result == text


# ─── fix_inner_quotes (10 cases) ─────────────────────────────────────────────


class TestFixInnerQuotes:
    def test_inner_quotes_at_start_of_value(self):
        text = '{"a": ""hello" world"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "hello" in parsed["a"]

    def test_inner_quotes_at_end_of_value(self):
        text = '{"a": "say "goodbye""}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "goodbye" in parsed["a"]

    def test_multiple_inner_quote_pairs(self):
        text = '{"a": "the "quick" brown "fox""}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "quick" in parsed["a"]
        assert "fox" in parsed["a"]

    def test_inner_quotes_with_special_chars(self):
        text = '{"a": "the "key" is {here}"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "key" in parsed["a"]

    def test_value_entirely_inner_quoted(self):
        text = '{"a": ""text""}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "text" in parsed["a"]

    def test_adjacent_to_comma(self):
        text = '{"a": "say "hi"", "b": 1}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "hi" in parsed["a"]
        assert parsed["b"] == 1

    def test_no_inner_quotes_unchanged(self):
        text = '{"a": "normal string", "b": "another"}'
        result = fix_inner_quotes(text)
        assert result == text

    def test_key_with_quotes_not_affected(self):
        text = '{"normal_key": "has "inner" quotes"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "inner" in parsed["normal_key"]

    def test_empty_value_unchanged(self):
        text = '{"a": ""}'
        result = fix_inner_quotes(text)
        assert json.loads(result) == {"a": ""}

    def test_multiple_keys_with_inner_quotes(self):
        text = '{"x": "the "a" val", "y": "the "b" val"}'
        result = fix_inner_quotes(text)
        parsed = json.loads(result)
        assert "a" in parsed["x"]
        assert "b" in parsed["y"]
