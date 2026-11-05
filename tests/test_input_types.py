import ast
import asyncio
from collections import UserString
from types import coroutine

import pytest

import outputguard as og
from outputguard.formats import parse_document
from outputguard.repairer import repair as raw_repair
from outputguard.retry import retry_prompt as raw_retry
from outputguard.validator import validate as raw_validate

FORMATS = ["json", "yaml", "toml", "python", "auto", "forced-json-off"]


class Uncoercible:
    @property
    def __class__(self):
        raise AssertionError("instance class was read")

    def __str__(self):
        raise AssertionError("input was coerced")

    def __len__(self):
        raise AssertionError("input length was read")

    def __iter__(self):
        raise AssertionError("input was iterated")


class SpoofString:
    @property
    def __class__(self):
        return str

    def __str__(self):
        raise AssertionError("fake string was coerced")


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize(
    "value_factory",
    [
        lambda: b"{}",
        lambda: bytearray(b"{}"),
        lambda: memoryview(b"{}"),
        lambda: UserString("{}"),
        lambda: ast.parse("{}", mode="eval"),
        Uncoercible,
        SpoofString,
    ],
)
def test_low_level_text_entrypoints_reject_non_strings(fmt, value_factory):
    value = value_factory()
    for call in (
        lambda: parse_document(value, fmt),
        lambda: raw_validate(value, True, fmt),
        lambda: raw_repair(value, format=fmt),
        lambda: raw_repair(value, format=fmt, report=True),
        lambda: og.repair(value, format=fmt),
        lambda: og.repair(value, format=fmt, report=True),
        lambda: raw_retry(value, True, [], fmt, include_message_history=False),
    ):
        with pytest.raises(TypeError, match="^text must be a string$"):
            call()


@pytest.mark.parametrize("operation", ["validate", "validate_repair", "repair"])
@pytest.mark.parametrize(
    "texts_factory",
    [
        lambda: "{}",
        lambda: b"{}",
        bytearray,
        lambda: memoryview(b""),
        lambda: {"{}"},
        lambda: iter(["{}"]),
        Uncoercible,
        lambda: None,
    ],
)
def test_batch_requires_a_sequence_without_consuming_iterators(operation, texts_factory):
    texts = texts_factory()
    with pytest.raises(TypeError, match="^texts must be a sequence of strings$"):
        if operation == "repair":
            og.repair_batch(texts)
        else:
            og.validate_batch(texts, True, repair=operation == "validate_repair")


@pytest.mark.parametrize("operation", ["validate", "validate_repair", "repair"])
def test_batch_snapshots_inputs_before_guard_can_mutate_them(operation):
    texts = ["{}", "null"]

    class MutatingGuard(og.OutputGuard):
        def validate(self, *args, **kwargs):
            texts[:] = [None]
            return super().validate(*args, **kwargs)

        def repair(self, *args, **kwargs):
            texts[:] = [None]
            return super().repair(*args, **kwargs)

    guard = MutatingGuard()
    result = (
        og.repair_batch(texts, guard=guard)
        if operation == "repair"
        else og.validate_batch(texts, True, guard=guard, repair=operation == "validate_repair")
    )
    assert result.summary.total == result.summary.valid == 2
    assert [item.input for item in result.results] == ["{}", "null"]
    assert texts == [None]
    assert og.validate_batch(("{}", "null"), True).summary.valid == 2


@pytest.mark.parametrize("value_factory", [Uncoercible, SpoofString])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_provider_non_string_errors_do_not_inspect_spoofed_instance_types(
    value_factory, asynchronous
):
    value = value_factory()
    options = dict(prompt="data", schema=True, generate=lambda *_: value)
    with pytest.raises(TypeError, match="^generate must return a string$"):
        if asynchronous:
            asyncio.run(og.guarded_generate_async(**options))
        else:
            og.guarded_generate(**options)


@pytest.mark.parametrize("value_factory", [Uncoercible, SpoofString])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_invalid_prompts_do_not_call_a_provider(value_factory, asynchronous):
    calls = []

    def generate(*args):
        calls.append(args)
        return "{}"

    options = dict(prompt=value_factory(), schema=True, generate=generate)
    with pytest.raises(TypeError, match="^prompt must be a string$"):
        if asynchronous:
            asyncio.run(og.guarded_generate_async(**options))
        else:
            og.guarded_generate(**options)
    assert calls == []


def test_strategy_cannot_return_an_object_pretending_to_be_a_string(monkeypatch):
    import outputguard.strategies as registry

    monkeypatch.setattr(
        registry,
        "ALL_STRATEGIES",
        [*registry.ALL_STRATEGIES, ("fake", lambda _: SpoofString()), ("recover", lambda _: "{}")],
    )
    result, report = og.OutputGuard(strategies=["fake", "recover"]).repair("{bad", report=True)
    assert result.text == "{}"
    assert report.steps[0].error == "Strategy must return a string"
    assert not report.steps[0].changed


def test_async_generation_keeps_custom_and_generator_based_awaitables():
    class AwaitableText:
        def __await__(self):
            async def value():
                return "{}"

            return value().__await__()

    @coroutine
    def legacy_value(value):
        if False:
            yield
        return value

    for provider in (lambda *_: AwaitableText(), lambda *_: legacy_value("{}")):
        result = asyncio.run(
            og.guarded_generate_async(
                prompt="data",
                schema=True,
                generate=provider,
                on_attempt=lambda _: legacy_value(None),
            )
        )
        assert result.valid and result.data == {}


def test_real_string_subclasses_are_accepted_without_coercion():
    class Text(str):
        def __str__(self):
            raise AssertionError("string subclass was coerced")

    text = Text("{}")
    assert og.validate(text, True).valid
    assert og.validate_batch((text,), True).summary.valid == 1
