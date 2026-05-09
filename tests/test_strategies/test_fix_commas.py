import json

from outputguard.strategies.fix_commas import apply


def test_trailing_comma_object():
    assert json.loads(apply('{"a": 1, "b": 2,}')) == {"a": 1, "b": 2}


def test_trailing_comma_array():
    assert json.loads(apply("[1, 2, 3,]")) == [1, 2, 3]


def test_nested_trailing_commas():
    text = '{"a": [1, 2,], "b": 3,}'
    assert json.loads(apply(text)) == {"a": [1, 2], "b": 3}


def test_no_trailing_commas():
    text = '{"a": 1}'
    assert apply(text) == text
