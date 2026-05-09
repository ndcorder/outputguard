import json

from outputguard.repairer import repair


def test_already_valid():
    result = repair('{"a": 1}')
    assert result.repaired is False
    assert result.text == '{"a": 1}'


def test_markdown_fenced():
    result = repair('```json\n{"a": 1}\n```')
    assert result.repaired is True
    assert json.loads(result.text) == {"a": 1}


def test_commentary():
    result = repair('Here is the JSON:\n{"a": 1}\nHope this helps!')
    assert result.repaired is True
    assert json.loads(result.text) == {"a": 1}


def test_multiple_issues():
    text = "```json\n{name: 'Alice', age: 30,}\n```"
    result = repair(text)
    assert result.repaired is True
    parsed = json.loads(result.text)
    assert parsed["name"] == "Alice"
    assert parsed["age"] == 30


def test_unrepairable():
    result = repair('this is not json at all and has no structure')
    assert result.repaired is False
