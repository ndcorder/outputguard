import asyncio
import json
import math
from pathlib import Path

import pytest

import outputguard as og
from outputguard.formats import format_label, normalize_format

FIXTURES = json.loads(
    (Path(__file__).parents[1] / "benchmarks/configuration_cases.json").read_text()
)
FORMATS = FIXTURES["formats"]
LIMITS = FIXTURES["attempt_limits"]


def document(case):
    return {
        "toml": "value=1",
        "yaml": "value: 1",
        "python": "{'value':1}",
    }.get(case.get("canonical"), '{"value":1}')


def format_error(case):
    return ValueError if isinstance(case["value"], str) else TypeError


@pytest.mark.parametrize("case", FORMATS, ids=lambda case: case["name"])
def test_format_normalization(case):
    if case["valid"]:
        assert normalize_format(case["value"]) == case["canonical"]
    else:
        with pytest.raises(format_error(case), match="[Ff]ormat"):
            normalize_format(case["value"])


@pytest.mark.parametrize("case", FORMATS, ids=lambda case: case["name"])
@pytest.mark.parametrize(
    "method",
    [
        "constructor",
        "validate",
        "repair",
        "repair_report",
        "validate_and_repair",
        "parse",
        "retry_prompt",
    ],
)
def test_guard_format_configuration_and_metadata(case, method):
    guard = og.OutputGuard(format="yaml")
    text, selected = document(case), case["value"]

    def call():
        if method == "constructor":
            return og.OutputGuard(format=selected)
        if method == "repair_report":
            return guard.repair(text, format=selected, report=True)
        if method == "retry_prompt":
            return guard.retry_prompt(text, True, [], format=selected)
        if method == "repair":
            return guard.repair(text, format=selected)
        return getattr(guard, method)(text, True, format=selected)

    if not case["valid"]:
        with pytest.raises(format_error(case), match="[Ff]ormat"):
            call()
        return
    result = call()
    if method == "constructor":
        assert result.format == selected and result.validate(text, True).data == {"value": 1}
    elif method == "parse":
        assert result == {"value": 1}
    elif method == "retry_prompt":
        assert result.endswith(f"Return ONLY the corrected {format_label(selected)}.")
    elif method == "repair_report":
        repair, report = result
        assert repair.format == report.format == selected
        assert not repair.repaired and report.success
    else:
        assert result.format == selected
        if method != "repair":
            assert result.valid and result.data == {"value": 1}
    assert guard.format == "yaml"


@pytest.mark.parametrize("case", FORMATS, ids=lambda case: case["name"])
def test_top_level_format_overrides(case):
    for method in (og.validate, og.validate_and_repair, og.parse, og.repair, og.retry_prompt):
        args = (document(case),) if method is og.repair else (document(case), True)
        if method is og.retry_prompt:
            args += ([],)
        if case["valid"]:
            result = method(*args, format=case["value"])
            if method is og.parse:
                assert result == {"value": 1}
            elif method is not og.retry_prompt:
                assert result.format == case["value"]
        else:
            with pytest.raises(format_error(case), match="[Ff]ormat"):
                method(*args, format=case["value"])
    if case["valid"]:
        result, report = og.repair(document(case), format=case["value"], report=True)
        assert result.format == report.format == case["value"]
        assert report.success
    else:
        with pytest.raises(format_error(case), match="[Ff]ormat"):
            og.repair(document(case), format=case["value"], report=True)


@pytest.mark.parametrize("case", FORMATS, ids=lambda case: case["name"])
@pytest.mark.parametrize("empty", [True, False])
@pytest.mark.parametrize("method", ["validate", "validate_and_repair", "repair"])
def test_batch_configuration_checked_even_without_inputs(case, empty, method):
    texts = [] if empty else [document(case)]
    for guard in (None, og.OutputGuard(format="yaml")):

        def call(guard=guard):
            if method == "repair":
                return og.repair_batch(texts, format=case["value"], guard=guard)
            return og.validate_batch(
                texts, True, format=case["value"], repair=method != "validate", guard=guard
            )

        if not case["valid"]:
            with pytest.raises(format_error(case), match="[Ff]ormat"):
                call()
            continue
        result = call()
        assert result.summary.total == result.summary.valid == len(texts)
        assert result.summary.formats == ({} if empty else {case["value"]: 1})
        assert [item.format for item in result.results] == [case["value"]] * len(texts)


@pytest.mark.parametrize("case", FORMATS, ids=lambda case: case["name"])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("repair", [False, True])
def test_generation_checks_format_before_calling_provider_or_observer(case, asynchronous, repair):
    generated, observed = [], []

    def generate(prompt, context):
        generated.append(context.attempt)
        return document(case)

    async def generate_async(prompt, context):
        return generate(prompt, context)

    options = dict(
        prompt="Return data",
        schema=True,
        guard=og.OutputGuard(format="yaml"),
        format=case["value"],
        max_retries=0,
        repair=repair,
        on_attempt=lambda attempt: observed.append(attempt.attempt),
    )

    def call():
        if asynchronous:
            return asyncio.run(og.guarded_generate_async(**options, generate=generate_async))
        return og.guarded_generate(**options, generate=generate)

    if not case["valid"]:
        with pytest.raises(format_error(case), match="[Ff]ormat"):
            call()
        assert generated == observed == []
    else:
        result = call()
        assert result.valid and result.data == {"value": 1} and result.format == case["value"]
        assert generated == observed == [0]


@pytest.mark.parametrize("case", LIMITS, ids=lambda case: case["name"])
def test_repair_attempt_limits(case):
    if not case["valid"]:
        with pytest.raises(ValueError, match="max_repair_attempts.*nonnegative safe integer"):
            og.OutputGuard(max_repair_attempts=case["value"])
        return
    guard = og.OutputGuard(max_repair_attempts=case["value"])
    result = guard.validate_and_repair('```json\n{"value":1}\n```', True)
    assert result.valid == (case["normalized"] > 0)
    assert result.repaired == (case["normalized"] > 0)


@pytest.mark.parametrize("case", LIMITS, ids=lambda case: case["name"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_retry_limits_before_provider_calls(case, asynchronous):
    generated, observed = [], []

    def generate(prompt, context):
        generated.append(context.attempt)
        return "true"

    async def generate_async(prompt, context):
        return generate(prompt, context)

    options = dict(
        prompt="Return data",
        schema=True,
        max_retries=case["value"],
        on_attempt=lambda attempt: observed.append(attempt.attempt),
    )

    def call():
        if asynchronous:
            return asyncio.run(og.guarded_generate_async(**options, generate=generate_async))
        return og.guarded_generate(**options, generate=generate)

    if not case["valid"]:
        with pytest.raises(ValueError, match="max_retries.*nonnegative safe integer"):
            call()
        assert generated == observed == []
    else:
        assert call().valid
        assert generated == observed == [0]


@pytest.mark.parametrize("limit", [math.nan, math.inf, -math.inf])
def test_nonfinite_attempt_limits_are_rejected(limit):
    with pytest.raises(ValueError, match="max_repair_attempts"):
        og.OutputGuard(max_repair_attempts=limit)
    with pytest.raises(ValueError, match="max_retries"):
        og.guarded_generate(
            prompt="x", schema=True, max_retries=limit, generate=lambda p, c: "true"
        )


@pytest.mark.parametrize("retries", [0, 1, 2, 3.0])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_retry_limit_counts_retries_after_the_initial_attempt(retries, asynchronous):
    contexts, observed = [], []

    def generate(prompt, context):
        contexts.append(context)
        return "true"

    async def generate_async(prompt, context):
        return generate(prompt, context)

    options = dict(
        prompt="Initial",
        schema=False,
        max_retries=retries,
        repair=False,
        on_attempt=lambda attempt: observed.append(attempt.attempt),
    )
    result = (
        asyncio.run(og.guarded_generate_async(**options, generate=generate_async))
        if asynchronous
        else og.guarded_generate(**options, generate=generate)
    )
    assert not result.valid and result.exhausted
    assert observed == [context.attempt for context in contexts] == list(range(int(retries) + 1))
    assert contexts[0].previous_result is None
    assert all(
        context.previous_result is result.attempts[index - 1].result
        for index, context in enumerate(contexts)
        if index
    )


@pytest.mark.parametrize("override", [None, "json", " YML "])
def test_absent_override_inherits_guard_and_preserves_spelling(override):
    guard = og.OutputGuard(format=" YML ")
    selected = " YML " if override is None else override
    text = "value: 1" if selected == " YML " else '{"value":1}'
    assert guard.validate(text, True, format=override).format == selected
    assert og.validate_batch([text], True, guard=guard, format=override).summary.formats == {
        selected: 1
    }
    assert og.repair_batch([text], guard=guard, format=override).summary.formats == {selected: 1}
    result = og.guarded_generate(
        prompt="x", schema=True, guard=guard, format=override, generate=lambda p, c: text
    )
    assert result.valid and result.format == selected
    assert guard.format == " YML "


def test_falsey_python_guard_is_still_used():
    class FalseyGuard(og.OutputGuard):
        def __bool__(self):
            return False

    guard = FalseyGuard(format="toml")
    assert og.validate_batch(["value=1"], True, guard=guard).results[0].data == {"value": 1}
    assert og.repair_batch(["value=1"], guard=guard).summary.formats == {"toml": 1}
    result = og.guarded_generate(
        prompt="x", schema=True, guard=guard, generate=lambda p, c: "value=1"
    )
    assert result.valid and result.format == "toml"

    async def generate(prompt, context):
        return "value=1"

    assert asyncio.run(
        og.guarded_generate_async(prompt="x", schema=True, guard=guard, generate=generate)
    ).valid


def test_mutated_python_guard_configuration_is_checked_before_generation():
    guard = og.OutputGuard()
    guard.max_repair_attempts = -1
    with pytest.raises(ValueError, match="max_repair_attempts"):
        og.guarded_generate(
            prompt="x",
            schema=True,
            guard=guard,
            generate=lambda p, c: pytest.fail("provider called"),
        )
    guard.max_repair_attempts = 0
    guard.format = ""
    with pytest.raises(ValueError, match="Unsupported format"):
        og.guarded_generate(
            prompt="x",
            schema=True,
            guard=guard,
            generate=lambda p, c: pytest.fail("provider called"),
        )


@pytest.mark.parametrize("empty", [True, False])
@pytest.mark.parametrize("case", LIMITS, ids=lambda case: case["name"])
def test_mutated_repair_limit_checked_before_validation_batch_work(case, empty):
    class TrackedGuard(og.OutputGuard):
        calls = 0

        def validate_and_repair(self, *args, **kwargs):
            self.calls += 1
            return super().validate_and_repair(*args, **kwargs)

    guard = TrackedGuard()
    guard.max_repair_attempts = case["value"]
    texts = [] if empty else ['{"value":1}']
    if case["valid"]:
        result = og.validate_batch(texts, True, guard=guard, repair=True)
        assert result.summary.valid == guard.calls == len(texts)
    else:
        with pytest.raises(ValueError, match="max_repair_attempts.*nonnegative safe integer"):
            og.validate_batch(texts, True, guard=guard, repair=True)
        assert guard.calls == 0


def test_validation_and_raw_repair_batches_do_not_consult_unused_repair_limit():
    guard = og.OutputGuard()
    guard.max_repair_attempts = -1
    assert og.validate_batch(["{}"], True, guard=guard).summary.valid == 1
    assert og.repair_batch(["{}"], guard=guard).summary.valid == 1
