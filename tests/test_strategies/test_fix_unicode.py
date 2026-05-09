import json

from outputguard.strategies.fix_unicode import apply


def test_incomplete_unicode():
    text = '{"a": "hello\\u00world"}'
    result = apply(text)
    json.loads(result)  # Should not raise


def test_hex_escape():
    text = '{"a": "\\x41\\x42"}'
    result = apply(text)
    data = json.loads(result)
    assert data["a"] == "AB"


def test_null_byte():
    text = '{"a": "hello\\0world"}'
    result = apply(text)
    data = json.loads(result)
    assert "hello" in data["a"]


def test_valid_unicode_preserved():
    text = '{"a": "caf\\u00e9"}'
    assert apply(text) == text


def test_no_escapes():
    text = '{"a": "hello"}'
    assert apply(text) == text
