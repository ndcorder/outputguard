"""Repeatable API benchmarks and normalized results for cross-runtime comparison."""

from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import re
import statistics
from pathlib import Path

from referencing.exceptions import Unresolvable

from benchmarks.comparison import assert_json_equal
from benchmarks.timing import environment_snapshot, make_timer, round_microseconds
from outputguard import (
    OutputGuard,
    SchemaEvaluationError,
    invalidate_schema,
    repair,
    repair_batch,
    retry_prompt,
    validate,
    validate_and_repair,
    validate_batch,
)
from outputguard.batch import BatchRepairResult, BatchValidationResult
from outputguard.models import RepairResult, ValidationError
from outputguard.report import RepairReport, StrategyApplication
from outputguard.strategies import get_strategies, get_strategy

CASES_PATH = Path(__file__).with_name("cases.json")


def run_case(case: dict):
    operation = case.get("operation", "validate_and_repair")
    schema = case.get("schema")
    if case.get("fresh_schema"):
        schema = json.loads(json.dumps(schema))
    if operation == "expect_evaluation_error":
        try:
            validate(case["text"], schema, format=case["format"])
        except SchemaEvaluationError:
            return {"evaluation_error": True}
        raise ValueError("Expected SchemaEvaluationError")
    if operation == "invalidate_schema":
        invalidate_schema(schema)
        return {"invalidated": True}
    if operation == "validate_invalidated":
        invalidate_schema(schema)
        return validate(case["text"], schema, format=case["format"])
    if operation == "expect_input_type":
        entry = case["entry"]
        input_schema = case.get("schema", True)
        try:
            if entry == "validate":
                validate(case["text"], input_schema)
            elif entry == "validate_and_repair":
                validate_and_repair(case["text"], input_schema)
            elif entry == "parse":
                OutputGuard().parse(case["text"], input_schema)
            elif entry == "repair":
                OutputGuard().repair(case["text"])
            elif entry == "retry_prompt":
                retry_prompt(case["text"], input_schema, [], include_message_history=False)
            elif entry == "repair_batch":
                repair_batch(case["texts"])
            elif entry in {"validate_batch", "validate_repair_batch"}:
                validate_batch(case["texts"], input_schema, repair=entry == "validate_repair_batch")
            else:
                raise ValueError(f"Unknown input entry: {entry}")
        except TypeError as error:
            if str(error) != case["expected"]["input_error"]:
                raise
            return {"input_error": str(error)}
        raise ValueError("Expected an input TypeError")
    if operation in {"report_diff", "strategy_diff", "step_diffs"}:
        before, after = case["before"], case["after"]
        step = StrategyApplication("demo", before != after, before, after)
        report = RepairReport(before, after, True, steps=[step])
        text = (
            report.diff
            if operation == "report_diff"
            else step.diff
            if operation == "strategy_diff"
            else report.step_diffs()
        )
        return {"diff_text": text}
    if operation == "strategy_apply":
        return {"strategy_text": get_strategy(case["strategy"])(case["text"])}
    if operation == "strategy_selection":
        return {"strategy_names": [name for name, _ in get_strategies(case["strategies"])]}
    if operation == "strategy_guard":
        return {"strategy_names": OutputGuard(strategies=case["strategies"]).strategy_names}
    if operation == "strategy_repair":
        return OutputGuard(strategies=case["strategies"]).validate_and_repair(case["text"], schema)
    if operation in {"public_repair", "public_repair_report"}:
        return repair(
            case["text"], format=case["format"], report=operation == "public_repair_report"
        )
    if operation in {"repair", "repair_report"}:
        guard = OutputGuard(strategies=case.get("strategies"), format=case["format"])
        if operation == "repair_report":
            return normalized(guard.repair(case["text"], report=True))
        return guard.repair(case["text"])
    if operation == "expect_unresolvable":
        try:
            validate_and_repair(case["text"], schema, format=case["format"])
        except Unresolvable:
            return {"schema_error": "unresolvable"}
        raise ValueError("Expected a schema lookup failure")
    if operation == "retry_prompt":
        return retry_prompt(
            case["text"],
            schema,
            [ValidationError(**error) for error in case.get("errors", [])],
            format=case.get("format", "json"),
            include_message_history=case.get("include_message_history", False),
        )
    if operation == "validate":
        return validate(case["text"], schema, format=case["format"])
    if operation in ("validate_batch", "repair_batch"):
        guard = OutputGuard(format=case["guard_format"]) if "guard_format" in case else None
        if operation == "validate_batch":
            return validate_batch(
                case["texts"],
                schema,
                format=case.get("format"),
                repair=case.get("repair", False),
                guard=guard,
            )
        return repair_batch(case["texts"], format=case.get("format"), guard=guard)
    if operation != "validate_and_repair":
        raise ValueError(f"Unknown operation: {operation}")
    return validate_and_repair(case["text"], schema, format=case["format"])


def normalized(result) -> dict:
    if isinstance(result, tuple):
        repaired, report = result
        return {
            "result": normalized(repaired),
            "candidate_text": report.candidate_text,
            "strategies_tried": report.strategies_tried,
            "strategy_errors": [step.error for step in report.steps if step.error is not None],
            "confidence": report.confidence,
        }
    if isinstance(result, RepairResult):
        return {
            "repaired": result.repaired,
            "text": result.text,
            "strategies": result.strategies_applied,
            "parse_failure": result.parse_error is not None,
            "format": result.format,
        }
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        return {"prompt": result}
    if isinstance(result, (BatchValidationResult, BatchRepairResult)):
        return {"summary": dataclasses.asdict(result.summary)}
    return {
        "valid": result.valid,
        "data": result.data,
        "repaired": result.repaired,
        "repaired_text": result.repaired_text,
        "strategies": result.strategies_applied,
        "parse_failure": result.parse_error is not None,
        "error_paths": sorted(error.path for error in result.errors),
        "error_values": [error.value for error in sorted(result.errors, key=lambda e: e.path)],
    }


def check_cases(cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        actual = normalized(run_case(case))
        assert_json_equal(actual, case["expected"], case["name"])
        results.append({"name": case["name"], **actual})
    return results


def positive_int(value: str) -> int:
    message = "must be a positive safe integer in base 10"
    if not re.fullmatch(r"[ \t\r\n\v\f]*\+?[0-9]+[ \t\r\n\v\f]*", value):
        raise argparse.ArgumentTypeError(message)
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(message) from error
    if parsed <= 0 or parsed > 2**53 - 1:
        raise argparse.ArgumentTypeError(message)
    return parsed


def main(argv=None, *, timer_factory=make_timer, snapshot=environment_snapshot) -> None:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--iterations", type=positive_int, default=200)
    parser.add_argument("--samples", type=positive_int, default=5)
    parser.add_argument("--results", action="store_true", help="Emit checked normalized results")
    parser.add_argument("--clock", choices=("wall", "cpu"), default="wall", help="Timing clock")
    parser.add_argument(
        "--case",
        dest="case_names",
        action="append",
        default=[],
        metavar="NAME",
        help="Run one named case; repeat to select multiple cases",
    )
    args = parser.parse_args(argv)
    cases = json.loads(CASES_PATH.read_text())
    requested = set(args.case_names)
    unknown = requested - {case["name"] for case in cases}
    if unknown:
        parser.error("unknown benchmark cases: " + ", ".join(sorted(unknown)))
    if requested:
        cases = [case for case in cases if case["name"] in requested]
    results = check_cases(cases)
    if args.results:
        print(json.dumps(results, indent=2))
        return

    now = timer_factory(args.clock)
    environment_start = snapshot()
    measurements = []
    for case in cases:
        for _ in range(50):
            run_case(case)
        durations = []
        for _ in range(args.samples):
            start = now()
            for _ in range(args.iterations):
                run_case(case)
            durations.append((now() - start) / args.iterations / 1000)
        measurements.append(
            {
                "name": case["name"],
                "schema_mode": (
                    "none"
                    if "schema" not in case or case.get("operation") == "invalidate_schema"
                    else "fresh"
                    if case.get("fresh_schema") or case.get("operation") == "validate_invalidated"
                    else "reused"
                ),
                "median_us": round_microseconds(statistics.median(durations)),
                "min_us": round_microseconds(min(durations)),
            }
        )
    print(
        json.dumps(
            {
                "runtime": f"Python {platform.python_version()}",
                "platform": platform.platform(),
                "iterations": args.iterations,
                "samples": args.samples,
                "warmup_iterations": 50,
                "clock": args.clock,
                "environment": {"start": environment_start, "end": snapshot()},
                "measurements": measurements,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
