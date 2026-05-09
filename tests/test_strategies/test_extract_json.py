import json

from outputguard.strategies.extract_json import apply


def test_extract_object():
    assert apply('Here is the JSON: {"a":1} Hope this helps') == '{"a":1}'


def test_extract_array():
    assert apply('[1,2,3]') == '[1,2,3]'


def test_nested_braces():
    text = 'Result: {"a": {"b": 1}} done'
    assert apply(text) == '{"a": {"b": 1}}'


def test_no_json():
    assert apply('no json here') == 'no json here'


def test_with_preceding_text():
    text = 'Sure! Here is what you asked for:\n{"name": "test"}\nLet me know!'
    result = apply(text)
    assert json.loads(result) == {"name": "test"}
