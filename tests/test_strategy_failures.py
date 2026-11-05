import asyncio
import gc
import inspect

import pytest

from outputguard import OutputGuard
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import ALL_STRATEGIES


def guard_with(monkeypatch, apply):
    monkeypatch.setattr(
        "outputguard.strategies.ALL_STRATEGIES",
        [*ALL_STRATEGIES, ("fault", apply), ("recover", lambda _: "{}")],
    )
    return OutputGuard(strategies=["fault", "recover"])


def test_async_strategy_results_are_closed_without_running(monkeypatch, recwarn):
    returned = []
    ran = []

    async def asynchronous():
        ran.append(True)
        raise RuntimeError("must not execute")

    def apply(text):
        value = asynchronous()
        returned.append(value)
        return value

    result, report = guard_with(monkeypatch, apply).repair("{bad", report=True)
    assert result.text == "{}" and report.success
    assert report.steps[0].error == "Strategy must return a string"
    assert not ran
    assert all(inspect.getcoroutinestate(value) == inspect.CORO_CLOSED for value in returned)
    returned.clear()
    gc.collect()
    assert not [warning for warning in recwarn if issubclass(warning.category, RuntimeWarning)]


def test_suspended_coroutine_is_left_with_its_owner(monkeypatch):
    class Suspend:
        def __await__(self):
            yield None

    async def asynchronous():
        await Suspend()
        return "{}"

    value = asynchronous()
    value.send(None)
    try:
        result, report = guard_with(monkeypatch, lambda _: value).repair("{bad", report=True)
        assert result.text == "{}" and report.steps[0].error == "Strategy must return a string"
        assert inspect.getcoroutinestate(value) == inspect.CORO_SUSPENDED
    finally:
        value.close()


@pytest.mark.parametrize("exception", [KeyboardInterrupt, SystemExit, asyncio.CancelledError])
def test_process_and_cancellation_exceptions_propagate(monkeypatch, exception):
    def apply(text):
        raise exception()

    with pytest.raises(exception):
        guard_with(monkeypatch, apply).repair("{bad")


def test_unprintable_exception_does_not_abort_later_repairs(monkeypatch):
    class BrokenError(Exception):
        def __str__(self):
            raise ValueError("broken formatter")

    def apply(text):
        raise BrokenError()

    result, report = guard_with(monkeypatch, apply).repair("{bad", report=True)
    assert result.text == "{}" and report.success
    assert report.steps[0].error == "Strategy failed"


def test_report_details_show_errors_and_keep_empty_candidates():
    report = RepairReport(
        original_text="{bad",
        final_text="{bad",
        success=False,
        steps=[
            StrategyApplication("fault", False, "{bad", "{bad", "boom"),
            StrategyApplication("empty", True, "{bad", ""),
        ],
    )
    assert report.candidate_text == ""
    assert report.diff == "" and report.confidence == 0
    assert "=== fault ===\nError: boom" in report.step_diffs()
    assert "=== empty ===" in report.step_diffs()
    assert report.steps[0].diff == ""
    assert RepairReport("{}", "{}", True).candidate_text == "{}"
