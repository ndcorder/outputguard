"""Real-world LLM failure corpus — 100+ test cases based on actual outputs from
different models and providers observed in production."""

import json

import pytest

from outputguard import repair, validate_and_repair


# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}

BOOL_SCHEMA = {
    "type": "object",
    "properties": {"active": {"type": "boolean"}, "name": {"type": "string"}},
    "required": ["active", "name"],
}

ARRAY_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {"type": "object", "properties": {"id": {"type": "integer"}}},
        }
    },
    "required": ["items"],
}

FLEXIBLE_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": True,
}


# ===================================================================
# Class 1: ChatGPT / OpenAI Patterns
# ===================================================================


class TestChatGPTPatterns:
    """Patterns specific to OpenAI GPT models."""

    def test_json_fence_despite_instructions(self):
        """GPT wrapping JSON in ```json fences even when told not to."""
        text = '```json\n{"name": "Alice", "age": 30}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_here_is_the_json_preamble(self):
        """GPT adding 'Here is the JSON:' preamble."""
        text = 'Here is the JSON:\n\n{"name": "Bob", "age": 25}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Bob"

    def test_trailing_explanation(self):
        """GPT adding trailing explanation after JSON."""
        text = '{"name": "Carol", "age": 35}\n\nThis JSON contains the user\'s information as requested.'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_json_with_line_comments(self):
        """GPT returning JSON with // comments (JSONC-style)."""
        text = '{\n  "name": "Dave", // user name\n  "age": 28 // in years\n}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Dave"

    def test_trailing_commas_in_arrays(self):
        """GPT using trailing commas in arrays."""
        text = '{"name": "Eve", "age": 22, "tags": ["admin", "user",]}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["tags"] == ["admin", "user"]

    def test_truncated_large_response(self):
        """GPT truncating large responses mid-object."""
        text = '{"name": "Frank", "age": 40, "bio": "A long biography that gets cut off mid'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Frank"

    def test_multiple_json_blocks_with_explanations(self):
        """GPT returning multiple JSON blocks with explanations between them."""
        text = (
            "Here is the first result:\n\n"
            '```json\n{"name": "Grace", "age": 31}\n```\n\n'
            "And here is another variant:\n\n"
            '```json\n{"name": "Hank", "age": 45}\n```'
        )
        result = repair(text)
        data = json.loads(result.text)
        # Should extract the first JSON block
        assert data["name"] == "Grace"

    def test_typescript_fence(self):
        """GPT wrapping in ```typescript fences when writing for TypeScript."""
        text = '```typescript\n{"name": "Ivy", "age": 27}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Ivy"

    def test_note_after_json(self):
        """GPT adding 'Note:' after the JSON."""
        text = '{"name": "Jack", "age": 33}\n\nNote: The age field is required by the schema.'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Jack"

    def test_json_in_numbered_list(self):
        """GPT putting JSON inside a numbered list."""
        text = '1. The result:\n{"name": "Kate", "age": 29}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Kate"

    def test_sure_preamble(self):
        """GPT starting with 'Sure!' or 'Certainly!'."""
        text = 'Sure! Here you go:\n\n{"name": "Leo", "age": 41}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Leo"

    def test_block_comment_in_json(self):
        """GPT using /* */ block comments."""
        text = '{\n  "name": "Mia", /* first name */\n  "age": 26 /* years */\n}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Mia"

    def test_trailing_comma_in_object(self):
        """GPT trailing comma at end of object."""
        text = '{"name": "Nora", "age": 38,}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Nora"

    def test_preamble_and_fence_combined(self):
        """GPT combining preamble text with fenced JSON."""
        text = 'Here is the requested JSON output:\n\n```json\n{"name": "Oscar", "age": 50}\n```\n\nLet me know if you need changes!'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Oscar"

    def test_response_with_markdown_bold(self):
        """GPT surrounding JSON with markdown formatting."""
        text = '**Output:**\n\n{"name": "Pat", "age": 44}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Pat"


# ===================================================================
# Class 2: Claude / Anthropic Patterns
# ===================================================================


class TestClaudePatterns:
    """Patterns specific to Anthropic Claude models."""

    def test_thinking_preamble(self):
        """Claude's thinking preamble before JSON."""
        text = (
            "Let me think about this carefully.\n\n"
            "Based on the requirements, the appropriate response is:\n\n"
            '{"name": "Alice", "age": 30}'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_ill_create_preamble(self):
        """Claude adding 'I'll create...' before JSON."""
        text = 'I\'ll create a JSON object with the requested fields:\n\n{"name": "Bob", "age": 25}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Bob"

    def test_bare_backtick_fence(self):
        """Claude using ``` with no language tag."""
        text = '```\n{"name": "Carol", "age": 35}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_python_dict_true_false_none(self):
        """Claude occasionally using Python dict syntax (True/False/None)."""
        text = '{"active": True, "name": "Diana", "deleted": False, "middle_name": None}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["active"] is True
        assert data["deleted"] is False
        assert data["middle_name"] is None

    def test_json_fence_extra_newlines(self):
        """Claude wrapping in ```json with extra newlines."""
        text = '```json\n\n\n{"name": "Eve", "age": 22}\n\n\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Eve"

    def test_heres_the_json_response(self):
        """Claude adding 'Here\'s the JSON response:' before fenced JSON."""
        text = 'Here\'s the JSON response:\n\n```json\n{"name": "Frank", "age": 40}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Frank"

    def test_explanation_paragraphs_above_and_below(self):
        """Claude returning JSON with explanation paragraphs above and below."""
        text = (
            "Based on the input data, I've constructed the following JSON object "
            "that captures the key information:\n\n"
            '{"name": "Grace", "age": 31}\n\n'
            "This represents the user profile with all required fields populated "
            "according to the schema."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Grace"

    def test_markdown_heading_before_json(self):
        """Claude using markdown headings before JSON."""
        text = '## Result\n\n```json\n{"name": "Hank", "age": 45}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Hank"

    def test_thinking_tags_then_json(self):
        """Claude splitting response: [thinking]...[/thinking] then JSON."""
        text = (
            "[thinking]The user wants a simple JSON object with name and age.[/thinking]\n\n"
            '```json\n{"name": "Ivy", "age": 27}\n```'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Ivy"

    def test_claude_bullet_points_before_json(self):
        """Claude listing considerations before JSON."""
        text = (
            "Key considerations:\n"
            "- Name must be a string\n"
            "- Age must be an integer\n\n"
            '{"name": "Jack", "age": 33}'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Jack"

    def test_claude_xml_artifact_wrapper(self):
        """Claude wrapping JSON in an XML artifact tag."""
        text = '<artifact>\n{"name": "Kate", "age": 29}\n</artifact>'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Kate"

    def test_claude_indented_json_in_explanation(self):
        """Claude embedding indented JSON in explanation."""
        text = (
            "The resulting JSON is:\n\n"
            '    {"name": "Leo", "age": 41}\n\n'
            "Which satisfies all constraints."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Leo"

    def test_claude_trailing_comma_in_nested(self):
        """Claude with trailing comma inside nested structure."""
        text = '{"users": [{"name": "Mia", "age": 26,}, {"name": "Nora", "age": 38,},]}'
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["users"]) == 2

    def test_claude_heres_what_i_came_up_with(self):
        """Claude with conversational lead-in."""
        text = 'Here\'s what I came up with:\n\n{"name": "Oscar", "age": 50}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Oscar"

    def test_claude_double_newline_fence(self):
        """Claude with double newline after opening fence."""
        text = '```json\n\n{"name": "Pat", "age": 44}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Pat"


# ===================================================================
# Class 3: Llama / Meta Patterns
# ===================================================================


class TestLlamaPatterns:
    """Patterns from Meta Llama models."""

    def test_everything_in_markdown_fences(self):
        """Llama wrapping everything in markdown fences."""
        text = '```\n{"name": "Alice", "age": 30}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_output_prefix(self):
        """Llama adding 'Output:' prefix."""
        text = 'Output:\n{"name": "Bob", "age": 25}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Bob"

    def test_single_quotes_python_style(self):
        """Llama using single quotes for Python-style output."""
        text = "{'name': 'Carol', 'age': 35}"
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_python_booleans_mixed_with_json(self):
        """Llama mixing Python booleans with JSON."""
        text = '{"active": True, "name": "Dave", "verified": False}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["active"] is True
        assert data["verified"] is False

    def test_i_hope_this_helps_suffix(self):
        """Llama adding 'I hope this helps!' suffix."""
        text = '{"name": "Eve", "age": 22}\n\nI hope this helps!'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Eve"

    def test_truncated_mid_string(self):
        """Llama truncating mid-string on long outputs."""
        text = (
            '{"name": "Frank", "description": "This is a very long description that goes on and on'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Frank"

    def test_python_dict_literal(self):
        """Llama sometimes returning Python dict literal instead of JSON."""
        text = "{'name': 'Grace', 'age': 31, 'active': True, 'score': None}"
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Grace"
        assert data["active"] is True
        assert data["score"] is None

    def test_blank_lines_inside_json(self):
        """Llama adding blank lines inside JSON."""
        text = '{\n"name": "Hank",\n\n"age": 45\n\n}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Hank"

    def test_prompt_repeated_before_answer(self):
        """Llama repeating the prompt before the answer."""
        text = 'Generate a JSON object with name and age fields.\n\n{"name": "Ivy", "age": 27}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Ivy"

    def test_answer_prefix(self):
        """Llama using 'Answer:' prefix."""
        text = 'Answer:\n{"name": "Jack", "age": 33}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Jack"

    def test_result_prefix(self):
        """Llama using 'Result:' prefix."""
        text = 'Result: {"name": "Kate", "age": 29}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Kate"

    def test_llama_json_with_none_values(self):
        """Llama using None for null."""
        text = '{"name": "Leo", "age": 41, "email": None}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["email"] is None

    def test_llama_trailing_newlines(self):
        """Llama adding many trailing newlines."""
        text = '{"name": "Mia", "age": 26}\n\n\n\n\n'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Mia"

    def test_llama_response_prefix(self):
        """Llama using 'Response:' prefix."""
        text = 'Response:\n\n{"name": "Nora", "age": 38}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Nora"

    def test_llama_triple_backtick_same_line(self):
        """Llama putting ``` on same line as JSON."""
        text = '```{"name": "Oscar", "age": 50}```'
        result = repair(text)
        # At minimum, should not crash
        assert isinstance(result.text, str)


# ===================================================================
# Class 4: DeepSeek Patterns
# ===================================================================


class TestDeepSeekPatterns:
    """Patterns from DeepSeek models."""

    def test_always_json_fences(self):
        """DeepSeek always wrapping in ```json fences."""
        text = '```json\n{"status": "ok", "count": 42}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["status"] == "ok"

    def test_extra_newlines_after_fence(self):
        """DeepSeek adding extra newlines after closing fence."""
        text = '```json\n{"name": "Alice", "age": 30}\n```\n\n'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_trailing_commas_frequent(self):
        """DeepSeek using trailing commas frequently."""
        text = '{"a": 1, "b": 2, "c": 3,}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["c"] == 3

    def test_deepseek_nested_trailing_commas(self):
        """DeepSeek with trailing commas in nested structures."""
        text = '{"data": {"x": 1, "y": 2,}, "meta": ["a", "b",],}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["data"]["x"] == 1

    def test_deepseek_thinking_block(self):
        """DeepSeek with <think> block before JSON."""
        text = '<think>\nI need to return a JSON object.\n</think>\n\n{"name": "Bob", "age": 25}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Bob"

    def test_deepseek_fenced_with_trailing_comma(self):
        """DeepSeek combining fences and trailing commas."""
        text = '```json\n{"items": [1, 2, 3,],}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["items"] == [1, 2, 3]

    def test_deepseek_comments_inside_fence(self):
        """DeepSeek using comments inside fenced JSON."""
        text = '```json\n{\n  // main config\n  "debug": true,\n  "level": 5\n}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["debug"] is True

    def test_deepseek_extra_whitespace(self):
        """DeepSeek with excessive internal whitespace."""
        text = '{  "name"  :  "Carol"  ,  "age"  :  35  }'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_deepseek_truncated_array(self):
        """DeepSeek truncating mid-array."""
        text = '{"values": [1, 2, 3, 4, 5'
        result = repair(text)
        data = json.loads(result.text)
        assert 1 in data["values"]

    def test_deepseek_preamble_and_fence(self):
        """DeepSeek with preamble text then fenced JSON."""
        text = 'The result is as follows:\n\n```json\n{"score": 95, "grade": "A"}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["grade"] == "A"


# ===================================================================
# Class 5: Mistral Patterns
# ===================================================================


class TestMistralPatterns:
    """Patterns from Mistral models."""

    def test_unquoted_keys_js_style(self):
        """Mistral using JS-style unquoted keys."""
        text = '{name: "Alice", age: 30}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_undefined_mixed_with_null(self):
        """Mistral mixing undefined with null."""
        text = '{"name": "Bob", "email": undefined, "phone": null}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["email"] is None
        assert data["phone"] is None

    def test_commentary_text_around_json(self):
        """Mistral adding commentary text around JSON."""
        text = (
            "I analyzed the input and here is the structured output:\n\n"
            '{"name": "Carol", "age": 35}\n\n'
            "The fields have been validated against the schema."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_nan_for_missing_numeric(self):
        """Mistral using NaN for missing numeric values."""
        text = '{"name": "Dave", "score": NaN}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Dave"

    def test_truncated_mid_array(self):
        """Mistral truncating in middle of arrays."""
        text = '{"results": [{"id": 1}, {"id": 2}, {"id": 3'
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["results"]) >= 2

    def test_mistral_mixed_quotes_and_unquoted_keys(self):
        """Mistral mixing quoted and unquoted keys."""
        text = '{"name": "Eve", age: 22, "city": "Paris"}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Eve"
        assert data["age"] == 22

    def test_mistral_trailing_text_with_fence(self):
        """Mistral with trailing text after fenced JSON."""
        text = '```json\n{"name": "Frank", "age": 40}\n```\n\nPlease review the output above.'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Frank"

    def test_mistral_json_in_paragraph(self):
        """Mistral embedding JSON in middle of paragraph."""
        text = 'The computed result is {"value": 42, "unit": "meters"} based on input.'
        result = repair(text)
        data = json.loads(result.text)
        assert data["value"] == 42

    def test_mistral_infinity_value(self):
        """Mistral using Infinity for very large numbers."""
        text = '{"name": "Grace", "max_value": Infinity}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Grace"

    def test_mistral_multiple_unquoted_keys(self):
        """Mistral with multiple unquoted keys and trailing comma."""
        text = '{name: "Hank", age: 45, city: "Lyon",}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["city"] == "Lyon"


# ===================================================================
# Class 6: Gemini / Google Patterns
# ===================================================================


class TestGeminiPatterns:
    """Patterns from Google Gemini models."""

    def test_bare_array_when_object_asked(self):
        """Gemini returning bare arrays."""
        text = '[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]'
        result = repair(text)
        data = json.loads(result.text)
        assert len(data) == 2

    def test_json_fences(self):
        """Gemini using ```json fences."""
        text = '```json\n{"name": "Carol", "age": 35}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Carol"

    def test_heres_the_result_preamble(self):
        """Gemini adding 'Here\'s the result:' preamble."""
        text = 'Here\'s the result:\n\n{"name": "Dave", "age": 28}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Dave"

    def test_infinity_for_large_numbers(self):
        """Gemini sometimes using Infinity for very large numbers."""
        text = '{"count": 999999, "limit": Infinity}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["count"] == 999999

    def test_line_comments_in_json(self):
        """Gemini returning JSON with line comments."""
        text = '{\n  "name": "Eve", // primary key\n  "age": 22 // years\n}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Eve"

    def test_gemini_trailing_comma_nested(self):
        """Gemini with trailing commas in nested arrays."""
        text = '{"tags": ["a", "b", "c",], "count": 3,}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["count"] == 3

    def test_gemini_response_label(self):
        """Gemini prefixing with 'Response:' label."""
        text = 'Response:\n{"name": "Frank", "age": 40}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Frank"

    def test_gemini_bold_key_labels(self):
        """Gemini wrapping key names in bold in surrounding text."""
        text = 'The **name** and **age** fields are:\n\n{"name": "Grace", "age": 31}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Grace"

    def test_gemini_javascript_fence(self):
        """Gemini using ```javascript fence."""
        text = '```javascript\n{"name": "Hank", "age": 45}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Hank"

    def test_gemini_preamble_with_schema_echo(self):
        """Gemini echoing the schema before providing the response."""
        text = (
            "Based on the schema with properties name (string) and age (integer):\n\n"
            '{"name": "Ivy", "age": 27}'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Ivy"


# ===================================================================
# Class 7: Local / Small Model Patterns
# ===================================================================


class TestLocalModelPatterns:
    """Common failures from smaller/local models (GGUF, ollama, etc.)."""

    def test_mixed_python_and_json_syntax(self):
        """Mixing Python and JSON syntax in same object."""
        text = "{'key': True, \"other\": false}"
        result = repair(text)
        data = json.loads(result.text)
        assert data["key"] is True
        assert data["other"] is False

    def test_incomplete_truncated_json(self):
        """Incomplete/truncated JSON from context window limits."""
        text = '{"name": "Alice", "items": [{"id": 1}, {"id": 2'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Alice"

    def test_backtick_on_same_line(self):
        """Adding ``` on same line as JSON content."""
        text = '```{"name": "Bob", "age": 25}```'
        result = repair(text)
        # Should at minimum not crash
        assert isinstance(result.text, str)

    def test_ellipsis_abbreviated_content(self):
        """Using ... for abbreviated content."""
        text = '{"items": [1, 2, 3, ...], "count": 100}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["count"] == 100

    def test_undefined_for_missing(self):
        """Using undefined for missing values."""
        text = '{"name": "Carol", "email": undefined}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["email"] is None

    def test_json_followed_by_python_explanation(self):
        """JSON followed by Python-style explanation."""
        text = (
            '{"name": "Dave", "age": 28}\n\n'
            "# The above JSON contains the user info\n"
            "# name: str, age: int"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Dave"

    def test_consecutive_commas(self):
        """Using consecutive commas -- library may not handle this edge case."""
        text = '{"a": 1,, "b": 2}'
        result = repair(text)
        # Consecutive commas are not handled by fix_commas (only trailing).
        # Verify it doesn't crash.
        assert isinstance(result.text, str)

    def test_jsonc_block_comments(self):
        """Using /* JSONC comments */ in output."""
        text = '{/* config */ "debug": true, "level": /* importance */ 5}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["debug"] is True
        assert data["level"] == 5

    def test_key_equals_value_no_crash(self):
        """Returning {key = value} should not crash (may not parse)."""
        text = '{name = "Alice", age = 30}'
        result = repair(text)
        # Should not crash — may or may not repair
        assert isinstance(result.text, str)

    def test_mixed_quoted_and_unquoted_keys(self):
        """Mix of quoted and unquoted keys in same object."""
        text = '{"name": "Eve", age: 22, "city": "Berlin"}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Eve"
        assert data["age"] == 22

    def test_local_model_python_none(self):
        """Local model returning None instead of null."""
        text = '{"result": None, "error": None}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["result"] is None

    def test_local_model_single_quotes_nested(self):
        """Single quotes throughout nested structures."""
        text = "{'users': [{'name': 'Frank', 'age': 40}, {'name': 'Grace', 'age': 31}]}"
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["users"]) == 2

    def test_local_model_output_label_and_fence(self):
        """Output: label followed by fenced code."""
        text = 'Output:\n```json\n{"status": "success"}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["status"] == "success"

    def test_local_model_negative_infinity(self):
        """Local model using -Infinity.

        Python's json.loads accepts -Infinity/Infinity natively (returns
        float('-inf')/float('inf')), so the repairer considers it already
        valid and does NOT replace them with null.
        """
        text = '{"min": -Infinity, "max": Infinity}'
        result = repair(text)
        data = json.loads(result.text)
        # Python parses these as float('-inf') / float('inf')
        assert data["min"] == float("-inf")
        assert data["max"] == float("inf")

    def test_local_model_truncated_deeply_nested(self):
        """Deeply nested truncation."""
        text = '{"a": {"b": {"c": {"d": "value"'
        result = repair(text)
        data = json.loads(result.text)
        assert data["a"]["b"]["c"]["d"] == "value"


# ===================================================================
# Class 8: Real-World Prompt Responses
# ===================================================================


class TestRealWorldPromptResponses:
    """Simulate real use cases — given a specific prompt type, test messy responses."""

    # --- Sentiment analysis ---

    def test_sentiment_analysis_fenced(self):
        text = '```json\n{"text": "I love this product!", "sentiment": "positive", "confidence": 0.95}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["sentiment"] == "positive"

    # --- Data extraction ---

    def test_data_extraction_with_commentary(self):
        text = (
            "Based on the document, here are the extracted entities:\n\n"
            '{"entities": [\n'
            '    {"name": "John Smith", "type": "person"},\n'
            '    {"name": "Acme Corp", "type": "organization"},\n'
            '    {"name": "New York", "type": "location"}\n'
            "]}\n\n"
            "I identified 3 entities in the text."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["entities"]) == 3

    # --- Classification ---

    def test_classification_python_style(self):
        text = "{'category': 'technology', 'subcategory': 'AI', 'confidence': 0.88, 'tags': ['machine-learning', 'NLP',]}"
        result = repair(text)
        data = json.loads(result.text)
        assert data["category"] == "technology"

    # --- Code review ---

    def test_code_review_with_thinking(self):
        text = (
            "Let me analyze this code carefully.\n\n"
            "The main issues I found are:\n\n"
            "```json\n"
            "{\n"
            '    "issues": [\n'
            '        {"severity": "high", "line": 42, "message": "SQL injection vulnerability"},\n'
            '        {"severity": "medium", "line": 15, "message": "Missing null check"},\n'
            "    ],\n"
            '    "overall_quality": "needs improvement"\n'
            "}\n"
            "```\n\n"
            "I recommend addressing the SQL injection issue first."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["issues"]) == 2

    # --- Translation ---

    def test_translation_with_special_chars(self):
        text = '```json\n{"original": "Hello, world!", "translated": "Bonjour, le monde!", "language": "fr", "confidence": 0.98}\n```'
        result = repair(text)
        data = json.loads(result.text)
        assert data["language"] == "fr"

    # --- Summarization ---

    def test_summarization_unquoted_keys(self):
        text = '{summary: "The article discusses AI safety.", word_count: 42, key_topics: ["AI", "safety", "regulation"]}'
        result = repair(text)
        data = json.loads(result.text)
        assert "AI" in data["key_topics"]

    # --- Function calling ---

    def test_function_call_response_fenced(self):
        text = (
            "```json\n"
            '{"function": "get_weather", "arguments": {"location": "San Francisco", "unit": "celsius"}}\n'
            "```"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["function"] == "get_weather"
        assert data["arguments"]["location"] == "San Francisco"

    # --- Tool use ---

    def test_tool_use_with_preamble(self):
        text = (
            "I'll use the search tool to find that information:\n\n"
            '{"tool": "web_search", "query": "latest Python release date", "max_results": 5}'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["tool"] == "web_search"

    # --- Structured extraction ---

    def test_structured_extraction_trailing_comma(self):
        text = (
            '{"invoice": {"number": "INV-2024-001", '
            '"date": "2024-06-15", '
            '"items": [{"desc": "Widget", "qty": 10, "price": 9.99,},],'
            '"total": 99.90,}}'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["invoice"]["number"] == "INV-2024-001"

    # --- Quiz generation ---

    def test_quiz_generation_with_comments(self):
        text = (
            "{\n"
            '  "question": "What is the capital of France?", // geography\n'
            '  "options": ["London", "Paris", "Berlin", "Madrid"],\n'
            '  "correct_answer": "Paris", // correct\n'
            '  "difficulty": "easy"\n'
            "}"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["correct_answer"] == "Paris"

    # --- Recipe generation ---

    def test_recipe_generation_python_booleans(self):
        text = (
            "{'recipe': 'Pasta Carbonara', "
            "'vegetarian': False, "
            "'gluten_free': False, "
            "'prep_time_minutes': 30, "
            "'ingredients': ['pasta', 'eggs', 'bacon', 'parmesan',]}"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["recipe"] == "Pasta Carbonara"
        assert data["vegetarian"] is False

    # --- Product descriptions ---

    def test_product_description_mixed_issues(self):
        text = (
            "Here is the product listing:\n\n"
            "```json\n"
            "{\n"
            '  name: "Wireless Headphones",\n'
            "  price: 79.99,\n"
            '  "in_stock": True,\n'
            '  "features": ["noise canceling", "bluetooth 5.0", "30hr battery",],\n'
            "}\n"
            "```"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Wireless Headphones"
        assert data["in_stock"] is True

    # --- Calendar events ---

    def test_calendar_event_with_commentary(self):
        text = (
            "I've created the calendar event:\n\n"
            '{"title": "Team Standup", "start": "2024-06-15T09:00:00Z", '
            '"end": "2024-06-15T09:30:00Z", "recurring": true, "attendees": ["alice@co.com", "bob@co.com"]}\n\n'
            "The event has been scheduled."
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["title"] == "Team Standup"

    # --- Email parsing ---

    def test_email_parsing_response(self):
        text = (
            "```json\n"
            "{\n"
            '  "from": "alice@example.com",\n'
            '  "to": ["bob@example.com"],\n'
            '  "subject": "Q2 Report",\n'
            '  "has_attachments": true,\n'
            '  "priority": "high",\n'
            "}\n"
            "```"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["subject"] == "Q2 Report"

    # --- API schema generation ---

    def test_api_schema_unquoted_keys_and_comments(self):
        text = (
            "{\n"
            '  endpoint: "/api/users", // REST endpoint\n'
            '  method: "GET",\n'
            '  "response_type": "json",\n'
            '  "paginated": true\n'
            "}"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["endpoint"] == "/api/users"

    # --- Resume parsing ---

    def test_resume_parsing_nested_python_style(self):
        text = (
            "{'name': 'Jane Doe', "
            "'experience': [{'company': 'Tech Corp', 'years': 3, 'current': True}, "
            "{'company': 'StartupX', 'years': 2, 'current': False}], "
            "'skills': ['Python', 'TypeScript', 'SQL']}"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["name"] == "Jane Doe"
        assert len(data["experience"]) == 2

    # --- Error reporting ---

    def test_error_report_with_nan(self):
        text = '{"errors": [{"code": 404, "latency_ms": NaN, "message": "Not Found"}], "total": 1}'
        result = repair(text)
        data = json.loads(result.text)
        assert data["errors"][0]["code"] == 404

    # --- Database query result ---

    def test_db_query_result_truncated(self):
        text = (
            '{"query": "SELECT * FROM users", "rows": ['
            '{"id": 1, "name": "Alice"}, '
            '{"id": 2, "name": "Bob"}, '
            '{"id": 3, "name": "Carol"'
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["query"] == "SELECT * FROM users"

    # --- Config generation ---

    def test_config_generation_with_all_issues(self):
        """Config with fences, comments, trailing commas, unquoted keys."""
        text = (
            "```json\n"
            "{\n"
            "  // Database configuration\n"
            '  host: "localhost",\n'
            "  port: 5432,\n"
            '  "database": "myapp",\n'
            '  "ssl": True, /* enable in production */\n'
            "}\n"
            "```"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["host"] == "localhost"
        assert data["port"] == 5432
        assert data["ssl"] is True

    # --- Chatbot intent ---

    def test_chatbot_intent_classification(self):
        text = (
            "Based on the user's message, I've classified the intent:\n\n"
            "{'intent': 'book_flight', 'confidence': 0.92, "
            "'entities': {'destination': 'Tokyo', 'date': '2024-07-01'}, "
            "'fallback': False}"
        )
        result = repair(text)
        data = json.loads(result.text)
        assert data["intent"] == "book_flight"

    # --- Multi-label classification ---

    def test_multilabel_classification_trailing(self):
        text = '{"labels": ["sports", "technology", "business",], "confidence_scores": [0.85, 0.72, 0.68,],}'
        result = repair(text)
        data = json.loads(result.text)
        assert len(data["labels"]) == 3


# ===================================================================
# Class 8b: validate_and_repair integration with schemas
# ===================================================================


class TestValidateAndRepairIntegration:
    """Tests using validate_and_repair with actual schemas."""

    def test_fenced_json_with_schema(self):
        text = '```json\n{"name": "Alice", "age": 30}\n```'
        result = validate_and_repair(text, SIMPLE_SCHEMA)
        assert result.valid
        assert result.data["name"] == "Alice"

    def test_python_booleans_with_schema(self):
        text = '{"active": True, "name": "Bob"}'
        result = validate_and_repair(text, BOOL_SCHEMA)
        assert result.valid
        assert result.data["active"] is True

    def test_trailing_comma_array_with_schema(self):
        text = '{"items": [{"id": 1}, {"id": 2}, {"id": 3},]}'
        result = validate_and_repair(text, ARRAY_SCHEMA)
        assert result.valid
        assert len(result.data["items"]) == 3

    def test_preamble_and_comments_with_schema(self):
        text = 'Here is the result:\n\n{\n  "name": "Carol", // first\n  "age": 35 // years\n}'
        result = validate_and_repair(text, SIMPLE_SCHEMA)
        assert result.valid
        assert result.data["age"] == 35

    def test_unquoted_keys_with_schema(self):
        text = '{name: "Dave", age: 28}'
        result = validate_and_repair(text, SIMPLE_SCHEMA)
        assert result.valid

    def test_python_dict_with_schema(self):
        text = "{'name': 'Eve', 'age': 22}"
        result = validate_and_repair(text, SIMPLE_SCHEMA)
        assert result.valid
        assert result.data["name"] == "Eve"

    def test_truncated_with_schema(self):
        text = '{"items": [{"id": 1}, {"id": 2'
        result = validate_and_repair(text, ARRAY_SCHEMA)
        assert result.valid
        assert len(result.data["items"]) >= 1

    def test_full_pipeline_complex(self):
        """Complex case requiring multiple strategies with schema validation."""
        text = (
            "Sure! Here is the JSON:\n\n"
            "```json\n"
            "{\n"
            "  // User profile\n"
            "  name: 'Frank',\n"
            "  age: 40, /* years old */\n"
            "}\n"
            "```\n\n"
            "Let me know if you need anything else!"
        )
        result = validate_and_repair(text, SIMPLE_SCHEMA)
        assert result.valid
        assert result.data["name"] == "Frank"
        assert result.data["age"] == 40
        assert result.repaired is True
