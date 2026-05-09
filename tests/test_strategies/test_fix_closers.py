import json

from outputguard.strategies.fix_closers import apply


def test_missing_brace():
    result = apply('{"a": 1')
    assert json.loads(result) == {"a": 1}


def test_missing_bracket_and_brace():
    result = apply('{"a": [1, 2')
    assert json.loads(result) == {"a": [1, 2]}


def test_already_balanced():
    text = '{"a": [1, 2]}'
    assert apply(text) == text
