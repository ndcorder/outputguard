"""Edge-case tests -- adversarial inputs and real-world LLM failure patterns."""

import json

import outputguard
from outputguard.repairer import repair


class TestRealWorldLLMOutputs:
    """Tests based on actual LLM failure modes observed in production."""

    def test_chatgpt_style_preamble(self, simple_schema):
        text = """Sure! Here is the JSON you requested:

```json
{
    "name": "Alice",
    "age": 30
}
```

I hope this helps! Let me know if you need anything else."""
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Alice"

    def test_claude_style_thinking(self, simple_schema):
        text = """I'll create a JSON object with the user's information.

{"name": "Bob", "age": 25}"""
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Bob"

    def test_llm_explains_after_json(self, simple_schema):
        text = '{"name": "Charlie", "age": 35}\n\nAs you can see, Charlie is 35 years old.'
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid

    def test_python_dict_literal(self, simple_schema):
        text = "{'name': 'Diana', 'age': 28}"
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Diana"

    def test_python_dict_with_booleans(self):
        schema = {
            "type": "object",
            "properties": {"active": {"type": "boolean"}, "name": {"type": "string"}},
            "required": ["active", "name"],
        }
        text = "{'active': True, 'name': 'Test'}"
        result = outputguard.validate_and_repair(text, schema)
        assert result.valid
        assert result.data["active"] is True

    def test_javascript_object_literal(self):
        schema = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
        text = "{x: 42}"
        result = outputguard.validate_and_repair(text, schema)
        assert result.valid
        assert result.data["x"] == 42

    def test_json_with_comments_and_trailing_commas(self, simple_schema):
        text = """{\n    // User information\n    "name": "Eve", /* first name */\n    "age": 22, // years old\n}"""
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Eve"

    def test_multiple_json_blocks_takes_first(self, simple_schema):
        text = '```json\n{"name": "First", "age": 1}\n```\n\n```json\n{"name": "Second", "age": 2}\n```'
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "First"

    def test_json_with_nan_and_infinity(self):
        text = '{"a": NaN, "b": Infinity, "c": -Infinity}'
        # Python's json.loads accepts NaN/Infinity natively, so validate
        # sees this as valid JSON.  The repair strategy correctly replaces
        # them with null when invoked directly.
        from outputguard.strategies.fix_values import apply

        repaired = apply(text)
        data = json.loads(repaired)
        assert data["a"] is None
        assert data["b"] is None
        assert data["c"] is None

    def test_deeply_nested_repair(self):
        schema = {
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {"value": {"type": "string"}},
                        }
                    },
                }
            },
        }
        text = "{level1: {level2: {value: 'deep'}}}"
        result = outputguard.validate_and_repair(text, schema)
        assert result.valid
        assert result.data["level1"]["level2"]["value"] == "deep"

    def test_json_in_bullet_point(self, simple_schema):
        text = '- Response: {"name": "Test", "age": 20}'
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid

    def test_large_array_with_issues(self):
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        }
        items = ", ".join(f'{{"id": {i}}}' for i in range(50))
        text = f"[{items},]"  # trailing comma
        result = outputguard.validate_and_repair(text, schema)
        assert result.valid
        assert len(result.data) == 50


class TestAdversarialInputs:
    """Test with intentionally tricky inputs."""

    def test_empty_string(self):
        result = repair("")
        assert result.repaired is False

    def test_only_whitespace(self):
        result = repair("   \n\t  ")
        assert result.repaired is False

    def test_only_braces(self):
        result = repair("{}")
        assert result.repaired is False  # Already valid
        assert json.loads(result.text) == {}

    def test_only_brackets(self):
        result = repair("[]")
        assert result.repaired is False
        assert json.loads(result.text) == []

    def test_nested_empty(self):
        result = repair('{"a": {}, "b": []}')
        assert result.repaired is False

    def test_very_deep_nesting(self):
        text = '{"a": ' * 20 + "1" + "}" * 20
        result = repair(text)
        assert result.repaired is False  # Already valid
        data = json.loads(result.text)
        assert data is not None

    def test_special_characters_in_strings(self):
        text = '{"emoji": "Hello 🙋🌍", "path": "C:\\\\Users\\\\test"}'
        result = repair(text)
        data = json.loads(result.text)
        assert "Hello" in data["emoji"]

    def test_url_in_value(self):
        text = '{"url": "https://example.com/path?q=1&r=2#anchor"}'
        result = repair(text)
        assert result.repaired is False
        assert json.loads(result.text)["url"].startswith("https://")

    def test_html_in_value(self):
        text = '{"html": "<div class=\\"test\\">Hello</div>"}'
        result = repair(text)
        assert result.repaired is False

    def test_multiline_string_value(self):
        text = '{"text": "line1\nline2\nline3"}'
        result = repair(text)
        assert result.repaired is True
        data = json.loads(result.text)
        assert "line1" in data["text"]

    def test_json_number_edge_cases(self):
        text = '{"a": 0, "b": -1, "c": 1.5e10, "d": -3.14}'
        result = repair(text)
        assert result.repaired is False
        data = json.loads(result.text)
        assert data["c"] == 1.5e10

    def test_null_values(self):
        text = '{"a": null, "b": null}'
        result = repair(text)
        assert result.repaired is False
        data = json.loads(result.text)
        assert data["a"] is None

    def test_boolean_values(self):
        text = '{"a": true, "b": false}'
        result = repair(text)
        assert result.repaired is False

    def test_mixed_array(self):
        text = '[1, "two", true, null, {"five": 5}]'
        result = repair(text)
        assert result.repaired is False
        assert len(json.loads(result.text)) == 5


class TestStrategyInteractions:
    """Test how strategies interact when multiple are needed."""

    def test_fences_plus_comments_plus_trailing_comma(self, simple_schema):
        text = '```json\n{\n  "name": "Test", // a name\n  "age": 25, // years\n}\n```'
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid

    def test_extract_plus_quotes_plus_keys(self, simple_schema):
        text = "The output is: {name: 'Alice', age: 30} and that's it."
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Alice"

    def test_all_strategies_combined(self, simple_schema):
        # Combines: fences + comments + trailing comma + single quotes + unquoted keys + Python bool
        text = """```json
{
    name: 'Grace', // first name
    age: 40, /* years */
}
```"""
        result = outputguard.validate_and_repair(text, simple_schema)
        assert result.valid
        assert result.data["name"] == "Grace"
        assert result.data["age"] == 40

    def test_repair_preserves_data_integrity(self, nested_schema):
        text = """```json
{
    "items": [
        {"name": "Widget A", "price": 19.99},
        {"name": "Widget B", "price": 29.99},
    ],
    "metadata": {
        "total": 2,
        "timestamp": "2024-06-15T10:30:00Z",
    }
}
```"""
        result = outputguard.validate_and_repair(text, nested_schema)
        assert result.valid
        assert len(result.data["items"]) == 2
        assert result.data["items"][0]["price"] == 19.99
        assert result.data["metadata"]["total"] == 2


class TestEdgeCasesInStrategies:
    """Edge cases for individual strategies through the repair pipeline."""

    def test_fence_with_extra_whitespace(self):
        text = '```json  \n  {"a": 1}  \n  ```'
        result = repair(text)
        assert result.repaired is True

    def test_fence_with_no_newline(self):
        # Edge case: fence with content on same line
        text = '```json{"a": 1}```'
        result = repair(text)
        # May or may not repair depending on regex -- just shouldn't crash
        assert isinstance(result.repaired, bool)

    def test_single_quote_with_escaped_apostrophe(self):
        from outputguard.strategies.fix_quotes import apply

        result = apply("{'key': 'it\\'s fine'}")
        data = json.loads(result)
        assert data["key"] == "it's fine"

    def test_single_quote_with_inner_double_quote(self):
        from outputguard.strategies.fix_quotes import apply

        result = apply("{'key': 'say \"hello\"'}")
        data = json.loads(result)
        assert data["key"] == 'say "hello"'

    def test_comment_in_url_string(self):
        from outputguard.strategies.remove_comments import apply

        text = '{"url": "https://api.example.com/v1/users"}'
        assert apply(text) == text

    def test_keys_with_dollar_sign(self):
        from outputguard.strategies.fix_keys import apply

        result = apply('{$id: 1, $type: "test"}')
        data = json.loads(result)
        assert data["$id"] == 1

    def test_closers_with_strings_containing_braces(self):
        from outputguard.strategies.fix_closers import apply

        # Use a raw string so \{ stays as literal backslash + brace in the text;
        # JSON requires valid escape sequences, so use a regex that json.loads
        # can actually parse (double-escaped backslashes).
        text = '{"regex": "\\\\{.*\\\\}", "data": [1, 2'
        result = apply(text)
        data = json.loads(result)
        assert data["data"] == [1, 2]

    def test_values_nan_in_string(self):
        from outputguard.strategies.fix_values import apply

        text = '{"msg": "NaN means Not a Number", "val": NaN}'
        result = apply(text)
        data = json.loads(result)
        assert "NaN" in data["msg"]  # Preserved in string
        assert data["val"] is None  # Replaced outside string

    def test_commas_in_strings_preserved(self):
        from outputguard.strategies.fix_commas import apply

        text = '{"msg": "a, b, c,", "x": 1,}'
        result = apply(text)
        data = json.loads(result)
        assert data["msg"] == "a, b, c,"  # Comma in string preserved
        assert data["x"] == 1
