import json

from outputguard.strategies.remove_comments import apply


def test_single_line_comment():
    text = '{"a": 1 // comment\n}'
    result = apply(text)
    assert json.loads(result) == {"a": 1}


def test_multi_line_comment():
    text = '{"a": /* inline */ 1}'
    result = apply(text)
    assert json.loads(result) == {"a": 1}


def test_url_preserved():
    text = '{"url": "http://example.com"}'
    assert apply(text) == text


def test_no_comments():
    text = '{"a": 1}'
    assert apply(text) == text
