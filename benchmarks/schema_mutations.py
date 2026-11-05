"""Shared workflows for updating a root schema and invalidating its validator."""

import copy
import json
from pathlib import Path

from referencing.exceptions import Unresolvable

import outputguard as og
from benchmarks.comparison import assert_json_equal

CASES_PATH = Path(__file__).with_name("schema_mutations.json")
METHODS = ("validate", "guard", "repair", "parse", "batch", "batch_repair")


def mutation_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def run_mutation_case(case: dict, method: str = "validate") -> dict:
    schema = copy.deepcopy(case["schema"])
    guard = og.OutputGuard()
    stages = []
    for stage in case["stages"]:
        for change in stage.get("changes", []):
            parent = schema
            for key in change["path"][:-1]:
                parent = parent[key]
            key = change["path"][-1]
            if change.get("remove"):
                del parent[key]
            else:
                parent[key] = copy.deepcopy(change["value"])
        for _ in range(stage.get("invalidate", 1 if "changes" in stage else 0)):
            assert og.invalidate_schema(schema) is None
        results = []
        for check in stage["checks"]:
            text, fmt = check["text"], check.get("format", "json")
            try:
                if method == "parse":
                    try:
                        data = guard.parse(text, schema, format=fmt)
                        result = {"valid": True, "data": data, "paths": []}
                    except og.SchemaValidationError as error:
                        result = {
                            "valid": False,
                            "data": error.data,
                            "paths": sorted(item.path for item in error.validation_errors),
                        }
                else:
                    if method in {"batch", "batch_repair"}:
                        validated = og.validate_batch(
                            [text], schema, guard=guard, format=fmt, repair=method == "batch_repair"
                        ).results[0]
                    elif method == "guard":
                        validated = guard.validate(text, schema, format=fmt)
                    elif method == "repair":
                        validated = guard.validate_and_repair(text, schema, format=fmt)
                    elif method == "validate":
                        validated = og.validate(text, schema, format=fmt)
                    else:
                        raise ValueError(f"Unknown mutation method: {method}")
                    assert validated.parse_error is None
                    result = {
                        "valid": validated.valid,
                        "data": validated.data,
                        "paths": sorted(item.path for item in validated.errors),
                    }
            except Unresolvable:
                result = {"lookup_error": True}
            assert_json_equal(result, check["expected"], f"{case['name']} {method}")
            results.append(result)
        stages.append(results)
    return {"name": case["name"], "stages": stages}


def check_mutation_cases(cases: list[dict], method: str = "validate") -> list[dict]:
    return [run_mutation_case(case, method) for case in cases]
