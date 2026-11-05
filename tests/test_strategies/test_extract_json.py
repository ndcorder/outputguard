import json

import pytest

from outputguard.strategies.extract_json import apply


def test_extract_object():
    assert apply('Here is the JSON: {"a":1} Hope this helps') == '{"a":1}'


def test_extract_array():
    assert apply("[1,2,3]") == "[1,2,3]"


def test_nested_braces():
    text = 'Result: {"a": {"b": 1}} done'
    assert apply(text) == '{"a": {"b": 1}}'


def test_no_json():
    assert apply("no json here") == "no json here"


def test_with_preceding_text():
    text = 'Sure! Here is what you asked for:\n{"name": "test"}\nLet me know!'
    result = apply(text)
    assert json.loads(result) == {"name": "test"}


@pytest.mark.parametrize(
    "text", ['"{}"', ' "[]" \t', "'[literal]'", '"unfinished [', '"escaped \\" []"']
)
def test_quoted_roots_are_not_container_fragments(text):
    assert apply(text) == text


def test_quoted_introduction_does_not_hide_a_following_fragment():
    assert apply('"[ignore]" prefix {"a":1') == '{"a":1'
