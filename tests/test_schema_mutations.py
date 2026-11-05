import asyncio
import copy
from dataclasses import asdict

import pytest

import outputguard as og
from benchmarks.schema_mutations import METHODS, mutation_cases, run_mutation_case


@pytest.mark.parametrize("case", mutation_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("method", METHODS)
def test_schema_mutation_contract(case, method):
    run_mutation_case(case, method)


def test_invalidation_applies_across_guards_and_preserves_old_diagnostics():
    schema = {"type": "integer"}
    guards = [og.OutputGuard(), og.OutputGuard()]
    failed = og.validate('"text"', schema)
    snapshot = copy.deepcopy(asdict(failed))
    for guard in guards:
        assert guard.validate("1", schema).valid
    schema["type"] = "string"
    before = copy.deepcopy(schema)
    assert og.invalidate_schema(schema) is None
    assert og.invalidate_schema(schema) is None
    assert schema == before
    for guard in guards:
        assert not guard.validate("1", schema).valid
        assert guard.validate('"text"', schema).valid
    assert og.validate('"text"', schema).valid
    assert asdict(failed) == snapshot


@pytest.mark.parametrize("asynchronous", [True, False])
@pytest.mark.parametrize("repair", [True, False])
def test_observer_can_invalidate_before_the_next_generation_attempt(asynchronous, repair):
    schema = {"type": "integer"}
    events = []

    def generate(prompt, context):
        events.append(("generate", context.attempt))
        return '"text"'

    def observe(attempt):
        events.append(("observe", attempt.attempt))
        if attempt.attempt == 0:
            schema["type"] = "string"
            og.invalidate_schema(schema)

    async def generate_async(prompt, context):
        return generate(prompt, context)

    async def observe_async(attempt):
        observe(attempt)

    options = dict(prompt="data", schema=schema, max_retries=1, repair=repair)
    result = (
        asyncio.run(
            og.guarded_generate_async(**options, generate=generate_async, on_attempt=observe_async)
        )
        if asynchronous
        else og.guarded_generate(**options, generate=generate, on_attempt=observe)
    )
    assert result.valid and result.data == "text" and len(result.attempts) == 2
    assert not result.attempts[0].result.valid
    assert result.attempts[0].result.errors[0].path == "$"
    assert events == [("generate", 0), ("observe", 0), ("generate", 1), ("observe", 1)]
