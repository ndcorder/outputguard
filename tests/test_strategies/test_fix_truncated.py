import json

from outputguard.strategies.fix_truncated import apply


def test_truncated_mid_string():
    text = '{"name": "Ali'
    result = apply(text)
    assert json.loads(result) == {"name": "Ali"}


def test_truncated_after_colon():
    text = '{"name": "Alice", "age":'
    result = apply(text)
    data = json.loads(result)
    assert data["name"] == "Alice"
    assert "age" in data


def test_truncated_mid_array():
    text = '{"items": [1, 2, 3'
    result = apply(text)
    assert json.loads(result) == {"items": [1, 2, 3]}


def test_truncated_after_comma():
    text = '{"a": 1, "b": 2,'
    result = apply(text)
    data = json.loads(result)
    assert data["a"] == 1


def test_truncated_nested():
    text = '{"user": {"name": "Bob", "address": {"city": "NYC"'
    result = apply(text)
    data = json.loads(result)
    assert data["user"]["name"] == "Bob"


def test_not_truncated():
    text = '{"a": 1}'
    assert apply(text) == text


def test_truncated_mid_key():
    text = '{"name": "Alice", "em'
    result = apply(text)
    data = json.loads(result)
    assert data["name"] == "Alice"
