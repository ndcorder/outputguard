"""Shared repair outcomes and fault injection through the public strategy registry."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from outputguard import OutputGuard, StrategyError, repair
from outputguard.strategies import ALL_STRATEGIES, get_strategies

CASES_PATH = Path(__file__).with_name("repair_cases.json")


def repair_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


@contextmanager
def custom_strategies(case):
    original = list(ALL_STRATEGIES)
    calls = {entry["name"]: 0 for entry in case["custom"]}

    async def asynchronous(entry):
        if entry["action"] == "async_throw":
            raise RuntimeError(entry["value"])
        return entry["value"]

    def create(entry):
        if entry["action"] not in {
            "throw",
            "strategy_throw",
            "return",
            "async_return",
            "async_throw",
        }:
            raise ValueError(f"Unknown fixture action: {entry['action']}")

        def apply(text):
            calls[entry["name"]] += 1
            if entry["action"] == "throw":
                raise RuntimeError(entry["value"])
            if entry["action"] == "strategy_throw":
                raise StrategyError(entry["value"], entry.get("strategy_name", entry["name"]))
            if entry["action"].startswith("async_"):
                return asynchronous(entry)
            return entry["value"]

        return apply

    try:
        ALL_STRATEGIES.extend((entry["name"], create(entry)) for entry in case["custom"])
        yield calls
    finally:
        ALL_STRATEGIES[:] = original


def run_repair_case(case: dict, *, report: bool = True, entrypoint: str = "guard") -> dict:
    if entrypoint not in {"guard", "module"}:
        raise ValueError(f"Unknown repair entry point: {entrypoint}")
    with custom_strategies(case) as calls:
        if entrypoint == "module":
            # The module helper uses the registry defaults; select this fixture's
            # controlled registry while the context manager owns restoration.
            ALL_STRATEGIES[:] = get_strategies(case["strategies"])
            outcome = repair(case["text"], format=case["format"], report=report)
        else:
            guard = OutputGuard(strategies=case["strategies"], format=case["format"])
            outcome = guard.repair(case["text"], report=report)
        if report:
            result, details = outcome
        else:
            result = outcome
        actual = {
            "result": {
                "repaired": result.repaired,
                "text": result.text,
                "strategies": result.strategies_applied,
                "parse_failure": result.parse_error is not None,
                "format": result.format,
            },
            "calls": calls,
        }
        if report:
            actual["report"] = {
                "success": details.success,
                "format": details.format,
                "original_text": details.original_text,
                "final_text": details.final_text,
                "candidate_text": details.candidate_text,
                "parse_failure": details.parse_error is not None,
                "steps": [
                    {
                        "name": step.name,
                        "changed": step.changed,
                        "input_text": step.input_text,
                        "output_text": step.output_text,
                        "error": step.error,
                    }
                    for step in details.steps
                ],
                "strategies_changed": details.strategies_applied,
                "strategies_tried": details.strategies_tried,
                "confidence": details.confidence,
                "summary": details.summary,
                "has_diff": bool(details.diff),
                "diff": details.diff,
                "step_diffs": details.step_diffs(),
            }
        return actual


def check_repair_cases(
    cases: list[dict], *, report: bool = True, entrypoint: str = "guard"
) -> list[dict]:
    from benchmarks.comparison import assert_json_equal

    results = []
    for case in cases:
        actual = run_repair_case(case, report=report, entrypoint=entrypoint)
        expected = {**case["expected"]}
        if not report:
            expected.pop("report")
        assert_json_equal(actual, expected, case["name"])
        results.append({"name": case["name"], **actual})
    return results
