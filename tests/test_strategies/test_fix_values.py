import json

from outputguard.strategies.fix_values import apply


def test_nan():
    assert json.loads(apply('{"a": NaN}')) == {"a": None}


def test_infinity():
    assert json.loads(apply('{"a": Infinity}')) == {"a": None}


def test_negative_infinity():
    assert json.loads(apply('{"a": -Infinity}')) == {"a": None}


def test_undefined():
    assert json.loads(apply('{"a": undefined}')) == {"a": None}


def test_nan_in_string_preserved():
    text = '{"a": "NaN is not a number"}'
    assert apply(text) == text
