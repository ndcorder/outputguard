"""Exact string strategy, report, and public-validation repair contracts."""

import json
from pathlib import Path

import outputguard as og
from benchmarks.comparison import assert_json_equal
from outputguard.strategies import get_strategy

CASES_PATH = Path(__file__).with_name("string_repairs.json")
METHODS = ("strategy", "report", "validate")


def string_repair_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def applicable_cases(cases: list[dict], method: str) -> list[dict]:
    if method not in METHODS:
        raise ValueError(f"Unknown string repair method: {method}")
    return [case for case in cases if method != "validate" or "public" in case]


def decoded(text: str) -> dict:
    try:
        return {"parse_failure": False, "data": json.loads(text)}
    except ValueError:
        return {"parse_failure": True, "data": None}


def run_string_repair_case(case: dict, method: str = "strategy") -> dict:
    text, fixed = case["text"], case["expected_text"]
    changed = text != fixed
    if method == "strategy":
        strategy = get_strategy(case["strategy"])
        output = strategy(text)
        actual = {"text": output, **decoded(output)}
        expected = {"text": fixed, "parse_failure": not case["valid"], "data": case["data"]}
        if case["valid"]:
            assert_json_equal(strategy(output), output, f"{case['name']} idempotence")
    elif method == "report":
        result, report = og.OutputGuard(strategies=[case["strategy"]]).repair(text, report=True)
        actual = {
            "text": result.text,
            "repaired": result.repaired,
            "strategies": result.strategies_applied,
            "parse_failure": result.parse_error is not None,
            "data": decoded(result.text)["data"],
            "candidate_text": report.candidate_text,
            "success": report.success,
            "steps": [
                {"name": step.name, "changed": step.changed, "text": step.output_text}
                for step in report.steps
            ],
        }
        expected = {
            "text": fixed if case["valid"] else text,
            "repaired": case["valid"] and changed,
            "strategies": [case["strategy"]] if case["valid"] and changed else [],
            "parse_failure": not case["valid"],
            "data": case["data"],
            "candidate_text": fixed,
            "success": case["valid"],
            "steps": []
            if case["source_valid"]
            else [{"name": case["strategy"], "changed": changed, "text": fixed}],
        }
    elif method == "validate":
        if "public" not in case:
            raise ValueError("No public validation outcome specified for this fixture")
        result = og.validate_and_repair(text, case.get("schema", {"const": case["public"]["data"]}))
        actual = {
            "valid": result.valid,
            "data": result.data,
            "repaired": result.repaired,
            "repaired_text": result.repaired_text,
            "strategies": result.strategies_applied,
            "original_text": result.original_text,
            "parse_failure": result.parse_error is not None,
            "error_paths": [error.path for error in result.errors],
        }
        expected = {"original_text": text, **case["public"]}
    else:
        raise ValueError(f"Unknown string repair method: {method}")
    assert_json_equal(actual, expected, f"{case['name']} {method}")
    return {"name": case["name"], **actual}


def check_string_repair_cases(cases: list[dict], method: str = "strategy") -> list[dict]:
    return [run_string_repair_case(case, method) for case in applicable_cases(cases, method)]
