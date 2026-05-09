import json

from outputguard.strategies.fix_newlines import apply


def test_literal_newline_in_string():
    # Create text with actual newline inside a JSON string value
    text = '{"a": "line1\nline2"}'
    result = apply(text)
    assert json.loads(result) == {"a": "line1\nline2"}


def test_no_newlines():
    text = '{"a": "hello"}'
    assert apply(text) == text
