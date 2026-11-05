from collections import UserDict

import pytest

import outputguard as og
import outputguard.validator as validator_module
from outputguard.retry import retry_prompt as raw_retry
from outputguard.validator import validate as raw_validate

FORMATS = ["json", "yaml", "toml", "python", "auto", "forced-json-off"]


class SpoofDict:
    @property
    def __class__(self):
        return dict

    def __iter__(self):
        raise AssertionError("schema was iterated")

    def __str__(self):
        raise AssertionError("schema was coerced")


class Uninspectable(SpoofDict):
    @property
    def __class__(self):
        raise AssertionError("instance class was read")


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("text", ["{}", "["])
@pytest.mark.parametrize(
    "factory", [lambda: None, tuple, set, bytes, UserDict, SpoofDict, Uninspectable, object]
)
def test_schema_types_are_checked_at_raw_and_public_entrypoints(factory, fmt, text):
    schema = factory()
    guard = og.OutputGuard(format=fmt)
    for call in (
        lambda: og.invalidate_schema(schema),
        lambda: raw_validate(text, schema, fmt),
        lambda: raw_retry(text, schema, [], fmt),
        lambda: og.validate(text, schema, format=fmt),
        lambda: guard.validate_and_repair(text, schema),
        lambda: guard.parse(text, schema),
        lambda: guard.retry_prompt(text, schema, [], include_message_history=False),
    ):
        with pytest.raises(TypeError, match="^schema must be an object or boolean$"):
            call()


def test_invalid_schema_is_rejected_before_the_parser_is_called(monkeypatch):
    def parse(*args):
        pytest.fail("parser was called")

    monkeypatch.setattr(validator_module, "parse_document", parse)
    with pytest.raises(TypeError, match="^schema must be an object or boolean$"):
        raw_validate("{}", None)


@pytest.mark.parametrize("repair", [True, False])
def test_invalid_schema_is_rejected_before_reading_batch_items(repair):
    class Unreadable(list):
        def __iter__(self):
            pytest.fail("batch was copied")

    with pytest.raises(TypeError, match="^schema must be an object or boolean$"):
        og.validate_batch(Unreadable(["{}"]), None, repair=repair)


def test_real_dict_subclasses_remain_supported():
    class Dictionary(dict):
        pass

    schema = Dictionary(type="integer")
    assert og.validate("1", schema).valid
    assert not og.validate('"wrong"', schema).valid
    assert "integer" in og.retry_prompt("1", Dictionary(items=schema), [])


@pytest.mark.parametrize("schema", [{"type": "unknown"}, {"minimum": "x"}, {"properties": []}])
def test_root_type_check_does_not_eagerly_validate_schema_keywords(schema):
    result = og.validate("[", schema)
    assert not result.valid and result.parse_error is not None
