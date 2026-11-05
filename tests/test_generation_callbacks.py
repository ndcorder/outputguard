import asyncio
import inspect
import json
from pathlib import Path

import pytest

import outputguard as og

FIXTURES = json.loads(
    (Path(__file__).parents[1] / "benchmarks/configuration_cases.json").read_text()
)


@pytest.mark.parametrize("callback", ["generate", "on_attempt"])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "failure_type", [RuntimeError, og.OutputGuardError, asyncio.CancelledError]
)
def test_callback_failures_propagate_unchanged_without_retrying(
    callback, asynchronous, failure_type
):
    failure = failure_type("callback failed")
    calls = {"generate": 0, "on_attempt": 0}

    def generate(*args):
        calls["generate"] += 1
        if callback == "generate":
            raise failure
        return "null"

    def observe(attempt):
        calls["on_attempt"] += 1
        if callback == "on_attempt":
            raise failure

    async def async_generate(*args):
        return generate(*args)

    async def async_observe(attempt):
        observe(attempt)

    options = dict(prompt="data", schema=True, max_retries=3, throw_on_failure=True)
    if asynchronous:
        # Catch at the API boundary: older asyncio runners replace cancellation
        # exceptions when a cancelled task escapes the event loop.
        async def invoke():
            with pytest.raises(failure_type) as caught:
                await og.guarded_generate_async(
                    **options, generate=async_generate, on_attempt=async_observe
                )
            return caught.value

        caught_failure = asyncio.run(invoke())
    else:
        with pytest.raises(failure_type) as caught:
            og.guarded_generate(**options, generate=generate, on_attempt=observe)
        caught_failure = caught.value
    assert caught_failure is failure
    assert calls == {"generate": 1, "on_attempt": int(callback == "on_attempt")}


@pytest.mark.parametrize("case", FIXTURES["callback_values"], ids=lambda case: case["name"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_noncallable_generation_callbacks_fail_before_provider_calls(case, asynchronous):
    observed, generated = [], []
    function = og.guarded_generate_async if asynchronous else og.guarded_generate

    def invoke(**options):
        result = function(prompt="x", schema=True, **options)
        return asyncio.run(result) if asynchronous else result

    with pytest.raises(TypeError, match="generate must be callable"):
        invoke(generate=case["value"], on_attempt=lambda attempt: observed.append(attempt))
    assert observed == []

    def generate(prompt, context):
        generated.append(context.attempt)
        return "true"

    if case["observer_valid"]:
        assert invoke(generate=generate, on_attempt=case["value"]).valid
        assert generated == [0]
    else:
        with pytest.raises(TypeError, match="on_attempt must be callable"):
            invoke(generate=generate, on_attempt=case["value"])
        assert generated == []


@pytest.mark.parametrize("case", FIXTURES["provider_results"], ids=lambda case: case["name"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_nonstring_provider_results_do_not_consume_retries_or_notify_observers(case, asynchronous):
    generated, observed = [], []

    def generate(prompt, context):
        generated.append(context.attempt)
        return case["value"]

    async def generate_async(prompt, context):
        return generate(prompt, context)

    options = dict(
        prompt="x", schema=True, max_retries=3, on_attempt=lambda attempt: observed.append(attempt)
    )
    with pytest.raises(TypeError, match="generate must return a string"):
        if asynchronous:
            asyncio.run(og.guarded_generate_async(**options, generate=generate_async))
        else:
            og.guarded_generate(**options, generate=generate)
    assert generated == [0] and observed == []


@pytest.mark.parametrize("asynchronous", [False, True])
def test_falsey_callable_observer_is_used(asynchronous):
    observed = []

    class Observer:
        def __bool__(self):
            return False

        def __call__(self, attempt):
            observed.append(attempt.attempt)

    options = dict(prompt="x", schema=True, generate=lambda p, c: "true", on_attempt=Observer())
    result = (
        asyncio.run(og.guarded_generate_async(**options))
        if asynchronous
        else og.guarded_generate(**options)
    )
    assert result.valid and observed == [0]


def test_sync_wrapper_rejects_async_callbacks_before_provider_calls():
    generated = []

    def generate(prompt, context):
        generated.append(context.attempt)
        return "true"

    async def async_generate(prompt, context):
        return generate(prompt, context)

    async def async_observe(attempt):
        pytest.fail("observer called")

    class AsyncProvider:
        async def __call__(self, prompt, context):
            return generate(prompt, context)

    for provider, observer in [
        (async_generate, None),
        (AsyncProvider(), None),
        (generate, async_observe),
    ]:
        with pytest.raises(TypeError, match="use guarded_generate_async"):
            og.guarded_generate(prompt="x", schema=True, generate=provider, on_attempt=observer)
    assert generated == []


@pytest.mark.parametrize("callback", ["generate", "on_attempt"])
def test_sync_wrapper_closes_unstarted_coroutines_returned_by_sync_callbacks(callback):
    returned = []

    async def async_value(value):
        return value

    def coroutine(value):
        result = async_value(value)
        returned.append(result)
        return result

    options = dict(prompt="x", schema=True, generate=lambda p, c: "true")
    if callback == "generate":
        options["generate"] = lambda p, c: coroutine("true")
    else:
        options["on_attempt"] = lambda attempt: coroutine(None)
    with pytest.raises(
        TypeError,
        match="generate must return a string"
        if callback == "generate"
        else "use guarded_generate_async",
    ):
        og.guarded_generate(**options)
    assert len(returned) == 1 and inspect.getcoroutinestate(returned[0]) == inspect.CORO_CLOSED
