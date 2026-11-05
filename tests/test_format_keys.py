import json

import pytest

import outputguard
from outputguard.formats import normalize_format


@pytest.mark.parametrize("key", ["constructor", "toString", "__proto__"])
def test_required_and_optional_properties_only_consider_mapping_keys(key):
    assert not outputguard.validate("{}", {"required": [key]}).valid
    assert outputguard.validate("{}", {"properties": {key: {"type": "string"}}}).valid
    assert outputguard.validate(json.dumps({key: "saved"}), {"required": [key]}).valid


@pytest.mark.parametrize(
    "format", ["constructor", "__proto__", "prototype", "toString", "hasOwnProperty"]
)
def test_unsupported_format_names_are_rejected(format):
    with pytest.raises(ValueError, match="Unsupported format"):
        normalize_format(format)
    with pytest.raises(ValueError, match="Unsupported format"):
        outputguard.validate("anything", {}, format=format)
    with pytest.raises(ValueError, match="Unsupported format"):
        outputguard.repair("anything", format=format)


@pytest.mark.parametrize("format", ["json", "yaml", "python"])
def test_dictionary_keys_named_after_javascript_prototype_properties_are_preserved(format):
    data = {"__proto__": {"age": 42}, "constructor": "saved", "toString": "retained"}
    text = (
        "__proto__:\n  age: 42\nconstructor: saved\ntoString: retained"
        if format == "yaml"
        else json.dumps(data)
    )
    result = outputguard.parse(text, {}, format=format)
    assert result == data
    assert "age" not in result


def test_duplicate_dictionary_keys_keep_the_last_value():
    result = outputguard.parse(
        "{'__proto__': {'age': 42}, '__proto__': 'last'}", {}, format="python"
    )
    assert result == {"__proto__": "last"}


def test_nested_dictionary_values_do_not_satisfy_required_properties():
    result = outputguard.validate(
        "{'__proto__': {'age': 42}}", {"required": ["age"]}, format="python"
    )
    assert not result.valid
    assert result.data == {"__proto__": {"age": 42}}
