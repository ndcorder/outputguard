import json

from outputguard.strategies.fix_quotes import apply


def test_single_quotes():
    result = apply("{'key': 'value'}")
    assert json.loads(result) == {"key": "value"}


def test_mixed_quotes():
    result = apply("{'key': \"value\"}")
    assert json.loads(result) == {"key": "value"}


def test_already_double_quotes():
    text = '{"key": "value"}'
    assert apply(text) == text
