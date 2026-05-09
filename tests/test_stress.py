"""Stress test battery -- 170+ parametrized cases covering every conceivable edge case."""

import json

import pytest

from outputguard import parse, repair, validate, validate_and_repair
from outputguard.exceptions import ParseError, SchemaValidationError

# -- reusable schemas --------------------------------------------------------

_OBJ_NAME_AGE = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}
_ARR_INT = {"type": "array", "items": {"type": "integer"}}
_OBJ_X_NUM = {
    "type": "object",
    "properties": {"x": {"type": "number", "minimum": 0, "maximum": 10}},
}
_OBJ_STATUS = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["active", "inactive"]}},
}
_OBJ_TAGS = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
}


# -- 1. Fence variations (16 cases) -----------------------------------------


class TestFenceVariations:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ('```json\n{"a":1}\n```', {"a": 1}),
            ('```JSON\n{"a":1}\n```', {"a": 1}),
            ('```jsonc\n{"a":1}\n```', {"a": 1}),
            ('```javascript\n{"a":1}\n```', {"a": 1}),
            ('```js\n{"a":1}\n```', {"a": 1}),
            ('```\n{"a":1}\n```', {"a": 1}),
            ('```json  \n{"a":1}\n```', {"a": 1}),
            ('```json\n  {"a":1}  \n```', {"a": 1}),
            ('```json\n{"a":1}\n```\n\nExtra text after', {"a": 1}),
            ('Some preamble\n```json\n{"a":1}\n```', {"a": 1}),
            ('```json\n{"nested": {"b": [1,2,3]}}\n```', {"nested": {"b": [1, 2, 3]}}),
            ('```typescript\n{"a":1}\n```', {"a": 1}),
            ('```python\n{"a":1}\n```', {"a": 1}),
            ('```json5\n{"a":1}\n```', {"a": 1}),
            ('```json\r\n{"a":1}\r\n```', {"a": 1}),
            ("```json\n[1,2,3]\n```", [1, 2, 3]),
        ],
    )
    def test_fence_variants(self, text, expected):
        assert json.loads(repair(text).text) == expected


# -- 2. Commentary extraction (15 cases) ------------------------------------


class TestCommentaryExtraction:
    @pytest.mark.parametrize(
        "text,expected_key",
        [
            ('Here is the JSON:\n{"name": "Alice"}', "name"),
            ('{"name": "Bob"}\n\nLet me know if you need changes!', "name"),
            ('Sure! I\'d be happy to help.\n\n{"result": true}\n\nAnything else?', "result"),
            ('The answer is:\n\n{"value": 42}\n\nMeaning of life.', "value"),
            ('## Response\n\n{"data": [1,2,3]}\n\n## Notes\nSome notes.', "data"),
            ('- Output: {"key": "val"}', "key"),
            ('1. {"step": "one"} is the first step', "step"),
            ('> {"quoted": true}', "quoted"),
            ('{"a":1} and {"b":2} are both valid', "a"),
            ('Best response:\n\n{"answer": "yes"}\n\nbecause reasons.', "answer"),
            ('Analyzing.\nConsidering.\nResponse:\n{"done": true}', "done"),
            ('Para 1.\n\nPara 2.\n\n{"deep": "value"}\n\nPara 3.', "deep"),
            ('Response:\n{"items": [{"id": 1}]}\nEnd.', "items"),
            ('OK here goes: {"x": 99}', "x"),
            ('{"solo": true}\n---\nfooter', "solo"),
        ],
    )
    def test_commentary_extraction(self, text, expected_key):
        assert expected_key in json.loads(repair(text).text)


# -- 3. Python literals (16 cases) ------------------------------------------


class TestPythonLiterals:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("{'a': True}", {"a": True}),
            ("{'a': False}", {"a": False}),
            ("{'a': None}", {"a": None}),
            ("{'a': True, 'b': False, 'c': None}", {"a": True, "b": False, "c": None}),
            ("{'key': 'value'}", {"key": "value"}),
            ("{'nested': {'a': True}}", {"nested": {"a": True}}),
            ("{'list': [True, False, None]}", {"list": [True, False, None]}),
            ("{'a': 1, 'b': 2,}", {"a": 1, "b": 2}),
            ("{'a': true, 'b': False}", {"a": True, "b": False}),
            ("{'x': {'y': 1,},}", {"x": {"y": 1}}),
            ("{'nums': [1, 2, 3,]}", {"nums": [1, 2, 3]}),
            ("{'empty': {}}", {"empty": {}}),
            ("{'arr': []}", {"arr": []}),
            ("{'s': 'hello world'}", {"s": "hello world"}),
            ("{'n': 42, 'f': 3.14}", {"n": 42, "f": 3.14}),
        ],
    )
    def test_python_literals(self, text, expected):
        assert json.loads(repair(text).text) == expected

    def test_python_with_commentary(self):
        assert json.loads(repair("Here's the dict:\n{'x': True}\nDone!").text)["x"] is True


# -- 4. JavaScript literals (10 cases) --------------------------------------


class TestJavaScriptLiterals:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ('{key: "value"}', {"key": "value"}),
            ("{a: 1, b: 2, c: 3}", {"a": 1, "b": 2, "c": 3}),
            ('{my_key: "val", other_key: 42}', {"my_key": "val", "other_key": 42}),
            ('{key: "value", // comment\n}', {"key": "value"}),
            ("{items: [1, 2, 3]}", {"items": [1, 2, 3]}),
            ('{nested: {inner: "v"}}', {"nested": {"inner": "v"}}),
            ("{flag: true, count: 0}", {"flag": True, "count": 0}),
            ("{x: null, y: null}", {"x": None, "y": None}),
            ('{msg: "hello world", n: -5}', {"msg": "hello world", "n": -5}),
            ('{arr: ["a", "b"], obj: {k: 1}}', {"arr": ["a", "b"], "obj": {"k": 1}}),
        ],
    )
    def test_js_literals(self, text, expected):
        assert json.loads(repair(text).text) == expected


# -- 5. Truncated outputs (15 cases) ----------------------------------------


class TestTruncatedOutputs:
    @pytest.mark.parametrize(
        "text",
        [
            '{"name": "Ali',
            '{"name": "Alice", "age":',
            '{"name": "Alice", "age": 30, "hobbies": ["read',
            '{"items": [{"id": 1}, {"id": 2',
            '{"a": {"b": {"c": {"d": "deep',
            '{"key": "value", ',
            '{"data": [1, 2, 3',
            '{"name": "Alice", "scores": [95, 87, ',
            '[{"id": 1}, {"id": 2}, {"id":',
            '{"config": {"enabled": true, "settings": {"timeout":',
            '{"text": "Hello wor',
            '{"a": 1, "b": 2, "c"',
            '{"items": [{"name": "Widget", "price": 19.99}, {"name": "Gad',
            "[1, 2, 3, ",
            '{"x": [{"y": [',
        ],
    )
    def test_truncated_produces_valid_json(self, text):
        result = repair(text)
        assert result.repaired
        json.loads(result.text)  # must not raise


# -- 6. Multiple issues combined (15 cases) ---------------------------------


class TestMultipleIssuesCombined:
    @pytest.mark.parametrize(
        "text",
        [
            "```json\n{'a': 1,}\n```",
            "```json\n{a: True, b: None,}\n```",
            "Here: {a: 'value', b: 42,}\nDone",
            "```json\n{name: 'Alice', age: 30,}\n```\nLet me know!",
            "Sure!\n{items: [1, 2, 3,], total: 3}",
            "```json\n{'x': 1, 'y': 2,}\n```",
            "```json\n{name: 'test', // comment\n}\n```",
            "Here's your data: {'items': [True, False, None,]}",
            '```json\n{"a": 1, /* comment */ "b": 2,}\n```',
            "Response:\n```json\n{'key': 'val',}\n```\nEnd.",
            "{a: 'x', b: 'y', // note\n}",
            "```json\n[{'id': 1}, {'id': 2},]\n```",
            "Output: {'enabled': True, 'count': 5,}",
            "```javascript\n{name: 'test', active: True}\n```",
            "Here: [1, 2, 3,] done.",
        ],
    )
    def test_combined_issues_repaired(self, text):
        result = repair(text)
        assert result.repaired
        assert isinstance(json.loads(result.text), (dict, list))


# -- 7. Adversarial strings -- valid JSON preserved (10 cases) ---------------


class TestAdversarialStrings:
    @pytest.mark.parametrize(
        "text",
        [
            '{"url": "https://example.com/path?a=1&b=2#hash"}',
            '{"template": "Hello {{name}}, welcome!"}',
            '{"code": "if (x) { return y; }"}',
            '{"html": "<div class=\\"test\\\\\\">text</div>"}',
            '{"emoji": "Hello 👋🌍🎉"}',
            '{"chinese": "你好世界"}',
            '{"empty_strings": {"a": "", "b": "", "c": ""}}',
            '{"nulls": {"a": null, "b": null}}',
            '{"bools": {"a": true, "b": false}}',
            '{"numbers": {"int": 0, "neg": -1, "float": 3.14, "exp": 1.5e10}}',
        ],
    )
    def test_valid_json_preserved(self, text):
        result = repair(text)
        assert not result.repaired
        assert json.loads(result.text) == json.loads(text)


# -- 8. Large inputs (6 cases) ----------------------------------------------


class TestLargeInputs:
    def test_large_object(self):
        obj = {f"key_{i}": f"value_{i}" for i in range(500)}
        result = repair(json.dumps(obj))
        assert not result.repaired and json.loads(result.text) == obj

    def test_large_array(self):
        result = repair(json.dumps(list(range(1000))))
        assert not result.repaired

    def test_large_fenced(self):
        obj = {f"key_{i}": i for i in range(200)}
        result = repair(f"```json\n{json.dumps(obj, indent=2)}\n```")
        assert result.repaired and json.loads(result.text) == obj

    def test_deeply_nested(self):
        obj: dict = {"level": 0}
        cur = obj
        for i in range(1, 30):
            cur["child"] = {"level": i}
            cur = cur["child"]
        assert not repair(json.dumps(obj)).repaired

    def test_large_array_trailing_comma(self):
        text = "[" + ", ".join(str(i) for i in range(200)) + ",]"
        result = repair(text)
        assert result.repaired and len(json.loads(result.text)) == 200

    def test_large_fenced_trailing_commas(self):
        body = "{\n" + "\n".join(f'  "k{i}": {i},' for i in range(100)) + "\n}"
        result = repair(f"```json\n{body}\n```")
        assert result.repaired and len(json.loads(result.text)) == 100


# -- 9. Schema validation (10 cases) ----------------------------------------


class TestSchemaValidation:
    @pytest.mark.parametrize(
        "text,schema,should_pass",
        [
            ('{"name":"A","age":1}', _OBJ_NAME_AGE, True),
            ('{"name":"A"}', _OBJ_NAME_AGE, False),
            ("[1,2,3]", _ARR_INT, True),
            ('[1,"two",3]', _ARR_INT, False),
            ('{"x": 1.5}', _OBJ_X_NUM, True),
            (
                '{"x": 15}',
                {"type": "object", "properties": {"x": {"type": "number", "maximum": 10}}},
                False,
            ),
            ('{"status":"active"}', _OBJ_STATUS, True),
            ('{"status":"unknown"}', _OBJ_STATUS, False),
            ('{"tags": ["a", "b"]}', _OBJ_TAGS, True),
            ('{"tags": []}', _OBJ_TAGS, False),
        ],
    )
    def test_schema_validation(self, text, schema, should_pass):
        assert validate(text, schema).valid == should_pass


# -- 10. validate_and_repair end-to-end (11 cases) --------------------------


class TestValidateAndRepairEndToEnd:
    @pytest.mark.parametrize(
        "text",
        [
            '```json\n{"name":"A","age":1}\n```',
            "{'name': 'A', 'age': 1}",
            '{name: "A", age: 1}',
            '{"name":"A","age":1,}',
            'Here: {"name":"A","age":1} done',
            "{name: 'A', age: 1, // person\n}",
            "```json\n{name: 'A', age: 1,}\n```\nEnjoy!",
            '{"name":"A","age":1',
        ],
    )
    def test_succeeds(self, text):
        r = validate_and_repair(text, _OBJ_NAME_AGE)
        assert r.valid and r.data["name"] == "A" and r.data["age"] == 1

    @pytest.mark.parametrize(
        "text",
        [
            '{"name":"A","age":"not_int"}',
            '{"name": 123, "age": 1}',
            '{"age": 1}',
        ],
    )
    def test_schema_fail(self, text):
        assert not validate_and_repair(text, _OBJ_NAME_AGE).valid


# -- 11. Idempotency (11 cases) ---------------------------------------------


class TestIdempotency:
    @pytest.mark.parametrize(
        "text",
        [
            '{"a": 1}',
            '{"name": "Alice", "age": 30}',
            "[1, 2, 3]",
            '{"nested": {"a": [1, 2]}}',
            "[]",
            "{}",
            '{"a": null, "b": true, "c": false}',
            '{"k": "v", "n": 0}',
            '[{"id": 1}, {"id": 2}]',
        ],
    )
    def test_repair_idempotent(self, text):
        result = repair(text)
        assert not result.repaired and result.text == text

    def test_double_repair_idempotent(self):
        first = repair("```json\n{name: 'Alice', age: 30,}\n```")
        assert first.repaired
        second = repair(first.text)
        assert not second.repaired and second.text == first.text

    def test_double_repair_python_bools(self):
        first = repair("{'active': True, 'count': None}")
        assert first.repaired
        second = repair(first.text)
        assert not second.repaired and second.text == first.text


# -- 12. Empty and garbage inputs (17 cases) --------------------------------


class TestEmptyAndGarbage:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "   ",
            "\n\n",
            "\t",
            "not json at all",
            "random gibberish xyz",
            "SELECT * FROM users",
            "<html><body>Hello</body></html>",
            "# Markdown heading",
            "def foo(): pass",
            "console.log('hi')",
            "---\ntitle: yaml\n---",
        ],
    )
    def test_garbage_input(self, text):
        result = repair(text)
        assert isinstance(result.repaired, bool)  # must not crash

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("null", None),
            ("true", True),
            ("false", False),
            ("42", 42),
            ('"just a string"', "just a string"),
        ],
    )
    def test_json_primitives(self, text, expected):
        result = repair(text)
        assert not result.repaired and json.loads(result.text) == expected


# -- 13. parse() raises on failure (4 cases) --------------------------------


class TestParseRaises:
    def test_parse_success(self):
        assert parse('{"name": "A", "age": 1}', _OBJ_NAME_AGE)["name"] == "A"

    def test_parse_repairs_and_returns(self):
        assert parse('```json\n{"name": "A", "age": 1}\n```', _OBJ_NAME_AGE)["name"] == "A"

    def test_parse_raises_parse_error(self):
        with pytest.raises(ParseError):
            parse("not json", _OBJ_NAME_AGE)

    def test_parse_raises_schema_validation_error(self):
        with pytest.raises(SchemaValidationError):
            parse('{"name": "A"}', _OBJ_NAME_AGE)


# -- 14. Trailing commas (6 cases) ------------------------------------------


class TestTrailingCommas:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ('{"a": 1,}', {"a": 1}),
            ('{"a": 1, "b": 2,}', {"a": 1, "b": 2}),
            ("[1, 2, 3,]", [1, 2, 3]),
            ('{"a": [1, 2,],}', {"a": [1, 2]}),
            ('{"a": {"b": 1,},}', {"a": {"b": 1}}),
            ('[{"a": 1,}, {"b": 2,},]', [{"a": 1}, {"b": 2}]),
        ],
    )
    def test_trailing_commas_fixed(self, text, expected):
        result = repair(text)
        assert result.repaired and json.loads(result.text) == expected


# -- 15. Comments (6 cases) -------------------------------------------------


class TestComments:
    @pytest.mark.parametrize(
        "text",
        [
            '{"a": 1} // comment',
            '{"a": 1, // inline\n"b": 2}',
            '/* header */\n{"a": 1}',
            '{"a": 1, /* mid */ "b": 2}',
            '{\n  // line comment\n  "a": 1\n}',
            '{"a": 1} /* trailing block */',
        ],
    )
    def test_comments_removed(self, text):
        result = repair(text)
        assert result.repaired and json.loads(result.text)["a"] == 1


# -- 16. RepairResult fields (4 cases) --------------------------------------


class TestRepairResultFields:
    def test_strategies_applied_populated(self):
        result = repair('```json\n{"a": 1}\n```')
        assert result.repaired and len(result.strategies_applied) > 0

    def test_parse_error_on_failure(self):
        result = repair("not valid json at all")
        assert not result.repaired and result.parse_error is not None

    def test_no_parse_error_on_success(self):
        result = repair('{"a": 1}')
        assert not result.repaired and result.parse_error is None

    def test_text_field_always_set(self):
        for text in ['{"a": 1}', "broken", "```json\n{}\n```"]:
            assert isinstance(repair(text).text, str)
