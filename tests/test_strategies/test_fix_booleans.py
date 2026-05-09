import json

from outputguard.strategies.fix_booleans import apply


def test_python_true():
    assert json.loads(apply('{"a": True}')) == {"a": True}


def test_python_false():
    assert json.loads(apply('{"a": False}')) == {"a": False}


def test_python_none():
    assert json.loads(apply('{"a": None}')) == {"a": None}


def test_mixed():
    result = json.loads(apply('{"x": True, "y": False, "z": None}'))
    assert result == {"x": True, "y": False, "z": None}


def test_inside_string_preserved():
    text = '{"a": "True is not False"}'
    assert apply(text) == text


def test_already_json():
    text = '{"a": true, "b": false, "c": null}'
    assert apply(text) == text
