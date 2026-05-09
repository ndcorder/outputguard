import json

from outputguard.strategies.fix_ellipsis import apply


def test_ellipsis_as_value():
    result = apply('{"a": ...}')
    assert json.loads(result) == {"a": None}


def test_ellipsis_array():
    result = apply('{"items": [1, 2, ...]}')
    data = json.loads(result)
    assert data["items"] == [1, 2]


def test_ellipsis_standalone_array():
    result = apply('[...]')
    assert json.loads(result) == []


def test_ellipsis_standalone_object():
    result = apply('{...}')
    assert json.loads(result) == {}


def test_ellipsis_in_string_preserved():
    text = '{"msg": "Loading..."}'
    assert apply(text) == text


def test_ellipsis_comment_style():
    result = apply('{"items": [1, 2, 3, // ... more items\n]}')
    data = json.loads(result)
    assert 1 in data["items"]


def test_no_ellipsis():
    text = '{"a": 1}'
    assert apply(text) == text
