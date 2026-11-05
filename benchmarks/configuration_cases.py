"""Shared configuration checks, including provider and observer call counts."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import outputguard as og
from outputguard.strategies import get_strategies

FIXTURES_PATH = Path(__file__).with_name("configuration_cases.json")


def configuration_cases() -> list[dict]:
    fixtures = json.loads(FIXTURES_PATH.read_text())
    cases = []

    def add(case, expected):
        case["expected"] = {"configuration_error": None, "generated": 0, "observed": 0, **expected}
        cases.append(case)

    for fixture in fixtures["formats"]:
        selected = fixture["value"]
        text = {"yaml": "value: 1", "toml": "value=1", "python": "{'value':1}"}.get(
            fixture.get("canonical"), '{"value":1}'
        )
        for operation in ("guard", "validate", "repair", "batch", "empty_batch", "generate"):
            expected = {"configuration_error": "format"}
            if fixture["valid"]:
                if operation == "guard":
                    expected = {"format": selected}
                elif operation in {"validate", "generate"}:
                    expected = {"valid": True, "data": {"value": 1}, "format": selected}
                    if operation == "generate":
                        expected.update(generated=1, observed=1)
                elif operation == "repair":
                    expected = {"format": selected, "repaired": False, "parse_failure": False}
                else:
                    empty = operation == "empty_batch"
                    expected = {
                        "total": 0 if empty else 1,
                        "valid": 0 if empty else 1,
                        "formats": {} if empty else {selected: 1},
                    }
            add(
                {
                    "name": f"format-{fixture['name']}-{operation}",
                    "operation": operation,
                    "format": selected,
                    "text": text,
                },
                expected,
            )

    for fixture in fixtures["attempt_limits"]:
        for operation, option in (("guard", "max_repair_attempts"), ("generate", "max_retries")):
            expected = {"configuration_error": "attempt_limit"}
            if fixture["valid"]:
                expected = (
                    {"format": "json"}
                    if operation == "guard"
                    else {
                        "valid": True,
                        "data": {"value": 1},
                        "format": "json",
                        "generated": 1,
                        "observed": 1,
                    }
                )
            add(
                {
                    "name": f"limit-{fixture['name']}-{option}",
                    "operation": operation,
                    "text": '{"value":1}',
                    "format": "json",
                    option: fixture["value"],
                },
                expected,
            )
    for fixture in fixtures["callback_values"]:
        for callback in ("generate", "on_attempt"):
            expected = {"configuration_error": "callback"}
            if callback == "on_attempt" and fixture["observer_valid"]:
                expected = {"valid": True, "data": {"value": 1}, "format": "json", "generated": 1}
            add(
                {
                    "name": f"callback-{fixture['name']}-{callback}",
                    "operation": "generate",
                    "format": "json",
                    "text": '{"value":1}',
                    "callback": callback,
                    "callback_value": fixture["value"],
                },
                expected,
            )
    for fixture in fixtures["provider_results"]:
        add(
            {
                "name": "provider-result-" + fixture["name"],
                "operation": "generate",
                "format": "json",
                "provider_result": fixture["value"],
            },
            {"configuration_error": "provider_result", "generated": 1},
        )
    for operation in ("guard", "validate", "repair", "batch", "empty_batch", "generate"):
        inherited = "json" if operation == "guard" else " YML "
        expected = {"format": inherited}
        if operation == "validate" or operation == "generate":
            expected.update(valid=True, data={"value": 1})
            if operation == "generate":
                expected.update(generated=1, observed=1)
        elif operation == "repair":
            expected.update(repaired=False, parse_failure=False)
        elif operation in {"batch", "empty_batch"}:
            empty = operation == "empty_batch"
            expected = {
                "total": 0 if empty else 1,
                "valid": 0 if empty else 1,
                "formats": {} if empty else {inherited: 1},
            }
        add(
            {
                "name": "null-inheritance-" + operation,
                "operation": operation,
                "format": None,
                "guard_format": " YML ",
                "text": "value: 1",
            },
            expected,
        )
    for fixture in fixtures["strategy_selections"]:
        for operation in ("strategy_registry", "guard", "repair_report", "repair", "generate"):
            for clean in (True,) if operation in {"guard", "strategy_registry"} else (True, False):
                valid = (
                    clean
                    or fixture["value"] is None
                    or (fixture["valid"] and "fix_commas" in fixture["selected"])
                )
                expected = {"configuration_error": fixture.get("error")}
                if fixture["valid"]:
                    if operation in {"guard", "strategy_registry"}:
                        expected.update(names=fixture["selected"])
                        if operation == "guard":
                            expected["format"] = "json"
                    elif operation in {"repair", "repair_report"}:
                        expected.update(
                            format="json", repaired=not clean and valid, parse_failure=not valid
                        )
                    else:
                        expected.update(
                            valid=valid,
                            data={"value": 1} if valid else None,
                            format="json",
                            generated=1,
                            observed=1,
                        )
                state = "clean" if clean else "broken"
                add(
                    {
                        "name": f"strategies-{fixture['name']}-{operation}-{state}",
                        "operation": operation,
                        "strategies": fixture["value"],
                        "format": "json",
                        "guard_format": "json",
                        "text": '{"value":1}' if clean else '{"value":1,}',
                    },
                    expected,
                )
    return cases


def _error_category(error: Exception) -> str:
    message = str(error)
    if isinstance(error, TypeError) and message in {
        "strategy name must be a string",
        "strategies must be a sequence of strategy names",
    }:
        return "strategy_type"
    if isinstance(error, ValueError) and message.startswith("Unknown strategy:"):
        return "strategy_name"
    if isinstance(error, (TypeError, ValueError)):
        if message.startswith("Unsupported format:") or message == "Format must be a string":
            return "format"
        if "must be a nonnegative safe integer" in message:
            return "attempt_limit"
        if message in {"generate must be callable", "on_attempt must be callable"}:
            return "callback"
        if message == "generate must return a string":
            return "provider_result"
    raise error


async def _run_case(case: dict, asynchronous: bool) -> dict:
    result = {"configuration_error": None, "generated": 0, "observed": 0}

    def generate(prompt, context):
        result["generated"] += 1
        return case.get("provider_result", case.get("text"))

    def observe(attempt):
        result["observed"] += 1

    try:
        operation = case["operation"]
        if operation == "strategy_registry":
            result["names"] = [name for name, _ in get_strategies(case["strategies"])]
        elif operation == "guard":
            kwargs = {"format": case["format"]}
            if "max_repair_attempts" in case:
                kwargs["max_repair_attempts"] = case["max_repair_attempts"]
            if "strategies" in case:
                kwargs["strategies"] = case["strategies"]
            guard = og.OutputGuard(**kwargs)
            result["format"] = guard.format
            if "strategies" in case:
                result["names"] = guard.strategy_names
        else:
            guard = og.OutputGuard(
                format=case.get("guard_format", "yaml"), strategies=case.get("strategies")
            )
            if operation == "generate":
                kwargs = dict(
                    prompt="Return data",
                    schema=True,
                    guard=guard,
                    format=case["format"],
                    generate=generate,
                    on_attempt=observe,
                    max_retries=case.get("max_retries", 0),
                )
                if "callback" in case:
                    kwargs[case["callback"]] = case["callback_value"]
                generated = (
                    await og.guarded_generate_async(**kwargs)
                    if asynchronous
                    else og.guarded_generate(**kwargs)
                )
                result.update(valid=generated.valid, data=generated.data, format=generated.format)
            elif operation == "validate":
                validated = guard.validate(case["text"], True, format=case["format"])
                result.update(valid=validated.valid, data=validated.data, format=validated.format)
            elif operation in {"repair", "repair_report"}:
                repaired = (
                    guard.repair(case["text"], format=case["format"], report=True)[0]
                    if operation == "repair_report"
                    else guard.repair(case["text"], format=case["format"])
                )
                result.update(
                    format=repaired.format,
                    repaired=repaired.repaired,
                    parse_failure=repaired.parse_error is not None,
                )
            elif operation in {"batch", "empty_batch"}:
                texts = [] if operation == "empty_batch" else [case["text"]]
                summary = og.validate_batch(texts, True, guard=guard, format=case["format"]).summary
                result.update(total=summary.total, valid=summary.valid, formats=summary.formats)
            else:
                raise ValueError(f"Unknown configuration operation: {operation}")
    except Exception as error:
        result["configuration_error"] = _error_category(error)
    return {"name": case["name"], **result}


def check_configuration_cases(cases: list[dict], *, asynchronous: bool) -> list[dict]:
    from benchmarks.comparison import assert_json_equal

    async def run():
        results = []
        for case in cases:
            result = await _run_case(case, asynchronous)
            assert_json_equal(result, {"name": case["name"], **case["expected"]}, case["name"])
            results.append(result)
        return results

    return asyncio.run(run())
