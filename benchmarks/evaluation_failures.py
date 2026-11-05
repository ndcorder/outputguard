"""Shared contracts for schema-engine stack exhaustion and callback behavior."""

import asyncio
import copy
import json
from pathlib import Path

import outputguard as og
from benchmarks.comparison import assert_json_equal
from outputguard.validator import validate as raw_validate

CASES_PATH = Path(__file__).with_name("evaluation_failures.json")
METHODS = (
    "raw",
    "validate",
    "guard",
    "repair",
    "parse",
    "batch",
    "batch_repair",
    "generate",
    "generate_no_repair",
)
MESSAGE = "Schema evaluation could not complete because of excessive recursion"


def failure_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


async def run_failure_case(
    case: dict, method: str = "validate", asynchronous: bool = False
) -> dict:
    schema = copy.deepcopy(case["schema"])
    fmt, text = case["format"], case["text"]
    guard = og.OutputGuard(format=fmt)
    counts = {"generated": 0, "observed": 0}

    def generate(*args):
        counts["generated"] += 1
        return text

    def observe(attempt):
        counts["observed"] += 1

    try:
        if method == "raw":
            raw_validate(text, schema, fmt)
        elif method == "validate":
            og.validate(text, schema, format=fmt)
        elif method == "guard":
            guard.validate(text, schema)
        elif method == "repair":
            guard.validate_and_repair(text, schema)
        elif method == "parse":
            guard.parse(text, schema)
        elif method in {"batch", "batch_repair"}:
            og.validate_batch([text], schema, guard=guard, repair=method == "batch_repair")
        elif method in {"generate", "generate_no_repair"}:
            options = dict(
                prompt="data",
                schema=schema,
                guard=guard,
                generate=generate,
                on_attempt=observe,
                max_retries=2,
                repair=method == "generate",
            )
            if asynchronous:
                await og.guarded_generate_async(**options)
            else:
                og.guarded_generate(**options)
        else:
            raise ValueError(f"Unknown evaluation method: {method}")
    except og.SchemaEvaluationError as error:
        result = {
            "name": case["name"],
            "message": str(error),
            "data": error.data,
            "schema_identity": error.schema is schema,
            "format": error.format,
            "cause": isinstance(error.__cause__, RecursionError),
            **counts,
        }
        expected = {
            "name": case["name"],
            "message": MESSAGE,
            "data": case["data"],
            "schema_identity": True,
            "format": fmt,
            "cause": True,
            "generated": int(method in {"generate", "generate_no_repair"}),
            "observed": 0,
        }
        assert_json_equal(result, expected, f"{case['name']} {method}")
        return result
    raise AssertionError(f"{case['name']} {method}: expected SchemaEvaluationError")


def check_failure_cases(
    cases: list[dict], method: str = "validate", asynchronous: bool = False
) -> list[dict]:
    async def run():
        return [await run_failure_case(case, method, asynchronous) for case in cases]

    return asyncio.run(run())
