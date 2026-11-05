# mypy: warn_unused_ignores = True
"""Static public API contracts, checked by the CI typecheck job."""

from typing_extensions import assert_type

import outputguard as og
from outputguard.repairer import repair as raw_repair


def strategy_error_types() -> None:
    error = og.StrategyError("failed", strategy_name="custom")
    base: og.OutputGuardError = error
    assert_type(error.strategy_name, str)
    assert_type(base, og.OutputGuardError)
    og.StrategyError("failed")  # type: ignore[call-arg]
    og.StrategyError("failed", strategy_name=None)  # type: ignore[arg-type]


def generation_error_types(result: og.GuardedGenerateResult) -> None:
    error = og.GuardedGenerationError("failed", result)
    base: og.OutputGuardError = error
    assert_type(error.result, og.GuardedGenerateResult)
    assert_type(base, og.OutputGuardError)


def repair_report_types(report: bool) -> None:
    assert_type(og.repair("{}"), og.RepairResult)
    assert_type(og.repair("{}", "yaml"), og.RepairResult)
    assert_type(og.repair("{}", format=None, report=False), og.RepairResult)
    assert_type(og.repair("{}", report=True), tuple[og.RepairResult, og.RepairReport])
    assert_type(og.repair("{}", "yaml", report=True), tuple[og.RepairResult, og.RepairReport])
    assert_type(
        og.repair("{}", report=report), og.RepairResult | tuple[og.RepairResult, og.RepairReport]
    )
    og.repair("{}", report="true")  # type: ignore[call-overload]

    guard = og.OutputGuard()
    assert_type(guard.repair("{}"), og.RepairResult)
    assert_type(guard.repair("{}", format=None), og.RepairResult)
    assert_type(guard.repair("{}", report=False), og.RepairResult)
    assert_type(guard.repair("{}", report=True), tuple[og.RepairResult, og.RepairReport])
    assert_type(
        guard.repair("{}", report=report), og.RepairResult | tuple[og.RepairResult, og.RepairReport]
    )
    guard.repair("{}", report="true")  # type: ignore[call-overload]

    assert_type(raw_repair("{}"), og.RepairResult)
    assert_type(raw_repair("{}", ["strip_fences"], report=False), og.RepairResult)
    assert_type(raw_repair("{}", report=True), tuple[og.RepairResult, og.RepairReport])
    assert_type(
        raw_repair("{}", report=report), og.RepairResult | tuple[og.RepairResult, og.RepairReport]
    )
    raw_repair("{}", report="true")  # type: ignore[call-overload]
