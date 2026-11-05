import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

import outputguard as og
import outputguard.evaluation as evaluation
import outputguard.validator as validator_module
from benchmarks.evaluation_failures import METHODS, failure_cases, run_failure_case


@pytest.mark.parametrize("case", failure_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("method", METHODS)
def test_schema_evaluation_failure_contract(case, method):
    asyncio.run(run_failure_case(case, method))


@pytest.mark.parametrize("case", failure_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("method", ["generate", "generate_no_repair"])
def test_async_generation_does_not_retry_or_observe_a_stack_failure(case, method):
    asyncio.run(run_failure_case(case, method, True))


def test_invalidation_allows_recovery_after_a_stack_failure():
    schema = {"$ref": "#"}
    with pytest.raises(og.SchemaEvaluationError) as caught:
        og.validate("{}", schema)
    assert isinstance(caught.value, og.OutputGuardError)
    schema.clear()
    schema["type"] = "integer"
    og.invalidate_schema(schema)
    assert og.validate("1", schema).valid
    assert not og.validate('"text"', schema).valid


def test_productive_recursion_and_parse_failures_remain_ordinary_results():
    schema = {"properties": {"value": {"type": "integer"}, "next": {"$ref": "#"}}}
    assert og.validate('{"next":{"value":1}}', schema).valid
    failed = og.validate('{"next":{"value":"text"}}', schema)
    assert not failed.valid and failed.errors[0].path == "$.next.value"
    malformed = og.validate("[", {"$ref": "#"})
    assert not malformed.valid and malformed.parse_error is not None


def test_deep_compilation_or_evaluation_failure_preserves_context():
    schema = {}
    for _ in range(20000):
        schema = {"not": schema}
    with pytest.raises(og.SchemaEvaluationError) as caught:
        og.validate("{}", schema)
    assert caught.value.schema is schema and caught.value.data == {}
    assert isinstance(caught.value.__cause__, RecursionError)


def test_reference_tracking_is_isolated_between_threads(monkeypatch):
    native = evaluation._native_ref
    rendezvous = Barrier(2)

    def paused(*args):
        rendezvous.wait(timeout=5)
        yield from native(*args)

    monkeypatch.setattr(evaluation, "_native_ref", paused)
    schema = {"definitions": {"value": {"type": "integer"}}, "$ref": "#/definitions/value"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: og.validate("1", schema).valid, range(2)))
    assert results == [True, True]


def test_reentrant_validation_uses_an_independent_reference_scope(monkeypatch):
    native = evaluation._native_ref
    schema = {"definitions": {"value": {"type": "integer"}}, "$ref": "#/definitions/value"}
    entered = False

    def reentrant(*args):
        nonlocal entered
        if not entered:
            entered = True
            assert og.validate("1", schema).valid
        yield from native(*args)

    monkeypatch.setattr(evaluation, "_native_ref", reentrant)
    assert og.validate("1", schema).valid and entered


@pytest.mark.parametrize("kind", [ValueError, KeyboardInterrupt, asyncio.CancelledError])
def test_non_recursion_errors_and_cancellation_propagate_unchanged(monkeypatch, kind):
    original = kind("original failure")

    def fail(*args):
        raise original

    monkeypatch.setattr(validator_module, "_schema_errors", fail)
    with pytest.raises(kind) as caught:
        og.validate("{}", {})
    assert caught.value is original


@pytest.mark.parametrize("recursion", [True, False])
def test_native_panic_is_normalized_only_when_it_reports_recursion(monkeypatch, recursion):
    panic_type = type("PanicException", (BaseException,), {"__module__": "pyo3_runtime"})
    original = panic_type(
        "__eq__ failed: RecursionError" if recursion else "unrelated native panic"
    )

    def fail(*args):
        raise original

    monkeypatch.setattr(validator_module, "_schema_errors", fail)
    with pytest.raises(og.SchemaEvaluationError if recursion else panic_type) as caught:
        og.validate("{}", {})
    assert (caught.value.__cause__ if recursion else caught.value) is original
