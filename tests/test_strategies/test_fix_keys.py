import json

from outputguard.strategies.fix_keys import apply


def test_unquoted_key():
    result = apply('{key: "value"}')
    assert json.loads(result) == {"key": "value"}


def test_underscore_key():
    result = apply("{my_key: 1}")
    assert json.loads(result) == {"my_key": 1}


def test_already_quoted():
    text = '{"key": "value"}'
    assert apply(text) == text


def test_multiple_unquoted_keys():
    result = apply('{name: "Alice", age: 30}')
    parsed = json.loads(result)
    assert parsed == {"name": "Alice", "age": 30}
