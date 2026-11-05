"""Exact Unicode strategy, report, and public-validation repair contracts."""

import json
from pathlib import Path

import outputguard as og
from benchmarks.comparison import assert_json_equal
from outputguard.strategies import get_strategy

CASES_PATH = Path(__file__).with_name("unicode_repairs.json")
METHODS = ("strategy", "report", "validate")


def unicode_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def applicable_cases(cases: list[dict], method: str) -> list[dict]:
    if method not in METHODS:
        raise ValueError(f"Unknown Unicode repair method: {method}")
    return [case for case in cases if method != "validate" or case["valid"]]


def decoded(text: str) -> dict:
    try:
        return {"parse_failure": False, "data": json.loads(text)}
    except ValueError:
        return {"parse_failure": True, "data": None}


def run_unicode_case(case: dict, method: str = "strategy") -> dict:
    text, fixed = case["text"], case["expected_text"]
    changed = text != fixed
    if method == "strategy":
        strategy = get_strategy("fix_unicode")
        output = strategy(text)
        actual = {"text": output, **decoded(output)}
        expected = {"text": fixed, "parse_failure": not case["valid"], "data": case["data"]}
        if case["valid"]:
            assert_json_equal(strategy(output), output, f"{case['name']} idempotence")
    elif method == "report":
        result, report = og.OutputGuard(strategies=["fix_unicode"]).repair(text, report=True)
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
            "strategies": ["fix_unicode"] if case["valid"] and changed else [],
            "parse_failure": not case["valid"],
            "data": case["data"],
            "candidate_text": fixed,
            "success": case["valid"],
            "steps": []
            if case["source_valid"]
            else [{"name": "fix_unicode", "changed": changed, "text": fixed}],
        }
    elif method == "validate":
        if not case["valid"]:
            raise ValueError("Public validation contracts require a complete repaired document")
        result = og.validate_and_repair(text, {"const": case["data"]})
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
        expected = {
            "valid": True,
            "data": case["data"],
            "repaired": changed,
            "repaired_text": fixed if changed else "",
            "strategies": ["fix_unicode"] if changed else [],
            "original_text": text,
            "parse_failure": False,
            "error_paths": [],
        }
    else:
        raise ValueError(f"Unknown Unicode repair method: {method}")
    assert_json_equal(actual, expected, f"{case['name']} {method}")
    return {"name": case["name"], **actual}


def check_unicode_cases(cases: list[dict], method: str = "strategy") -> list[dict]:
    return [run_unicode_case(case, method) for case in applicable_cases(cases, method)]
