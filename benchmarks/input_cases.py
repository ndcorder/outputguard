"""Shared input-type contracts, including preflight and provider call counts."""

import asyncio
import json
from pathlib import Path

import outputguard as og
from outputguard.guard import OutputGuard

CASES_PATH = Path(__file__).with_name("input_cases.json")
METHODS = (
    "validate",
    "validate_and_repair",
    "parse",
    "repair",
    "repair_report",
    "retry_prompt",
    "retry_prompt_no_history",
)
BATCH_METHODS = ("validate_batch", "validate_repair_batch", "repair_batch")


def input_cases() -> list[dict]:
    fixtures = json.loads(CASES_PATH.read_text())
    cases = []

    def add(case, expected):
        case["expected"] = {
            "error": None,
            "error_type": None,
            "processed": 0,
            "generated": 0,
            "observed": 0,
            **expected,
        }
        cases.append(case)

    def error(message):
        return {"error": message, "error_type": "TypeError"}

    for fixture in fixtures["invalid_texts"]:
        for fmt in fixtures["formats"]:
            for method in METHODS:
                for style in ("guard", "top"):
                    if method == "repair_report" and style == "top":
                        continue
                    add(
                        {
                            "name": f"text-{fixture['name']}-{fmt}-{style}-{method}",
                            "operation": method,
                            "style": style,
                            "format": fmt,
                            "text": fixture["value"],
                        },
                        error("text must be a string"),
                    )
            for method in BATCH_METHODS:
                for index in (0, 1):
                    texts = ["{}"] * index + [fixture["value"]]
                    add(
                        {
                            "name": f"item-{fixture['name']}-{fmt}-{method}-{index}",
                            "operation": method,
                            "format": fmt,
                            "texts": texts,
                        },
                        error(f"texts[{index}] must be a string"),
                    )
        for repair in (True, False):
            add(
                {
                    "name": f"prompt-{fixture['name']}-{str(repair).lower()}",
                    "operation": "generate",
                    "format": "json",
                    "prompt": fixture["value"],
                    "repair": repair,
                },
                error("prompt must be a string"),
            )

    for fixture in fixtures["invalid_batch_containers"]:
        for fmt in fixtures["formats"]:
            for method in BATCH_METHODS:
                add(
                    {
                        "name": f"container-{fixture['name']}-{fmt}-{method}",
                        "operation": method,
                        "format": fmt,
                        "texts": fixture["value"],
                    },
                    error("texts must be a sequence of strings"),
                )

    for doc in fixtures["documents"]:
        methods = ("validate",) if doc["parse_failure"] else METHODS
        for method in methods:
            for style in ("guard", "top"):
                if method == "repair_report" and style == "top":
                    continue
                expected = {}
                if method in {"validate", "validate_and_repair"}:
                    expected = {
                        "valid": not doc["parse_failure"],
                        "data": doc["data"],
                        "parse_failure": doc["parse_failure"],
                        "original_text": doc["text"],
                        "format": doc["format"],
                    }
                elif method == "parse":
                    expected = {"data": doc["data"]}
                elif method.startswith("repair"):
                    expected = {
                        "repaired": False,
                        "text": doc["text"],
                        "parse_failure": False,
                        "format": doc["format"],
                    }
                    if method == "repair_report":
                        expected.update(report_success=True, report_original=doc["text"])
                else:
                    history = method != "retry_prompt_no_history"
                    expected = {"history": history, "contains_text": True if history else None}
                add(
                    {
                        "name": f"document-{doc['name']}-{style}-{method}",
                        "operation": method,
                        "style": style,
                        "format": doc["format"],
                        "text": doc["text"],
                    },
                    expected,
                )
        if not doc["parse_failure"]:
            for method in BATCH_METHODS:
                for count in (0, 2):
                    expected = {
                        "processed": count,
                        "texts": [doc["text"]] * count,
                        "total": count,
                        "valid": count,
                        "formats": {doc["format"]: count} if count else {},
                    }
                    if method != "repair_batch":
                        expected["data"] = [doc["data"]] * count
                    add(
                        {
                            "name": f"batch-{doc['name']}-{method}-{count}",
                            "operation": method,
                            "format": doc["format"],
                            "texts": [doc["text"]] * count,
                        },
                        expected,
                    )

    for index, prompt in enumerate(fixtures["valid_prompts"]):
        for repair in (True, False):
            add(
                {
                    "name": f"valid-prompt-{index}-{str(repair).lower()}",
                    "operation": "generate",
                    "format": "json",
                    "prompt": prompt,
                    "repair": repair,
                },
                {"valid": True, "generated": 1, "observed": 1},
            )
    for fixture in fixtures["invalid_schemas"]:
        for fmt in fixtures["formats"]:
            clean = "" if fmt == "toml" else "{}"
            for state, text in (("clean", clean), ("broken", "[")):
                for method in (
                    "validate",
                    "validate_and_repair",
                    "parse",
                    "retry_prompt",
                    "retry_prompt_no_history",
                ):
                    for style in ("guard", "top"):
                        add(
                            {
                                "name": f"schema-{fixture['name']}-{fmt}-{state}-{style}-{method}",
                                "operation": method,
                                "style": style,
                                "format": fmt,
                                "schema": fixture["value"],
                                "text": text,
                            },
                            error("schema must be an object or boolean"),
                        )
            for method in ("validate_batch", "validate_repair_batch"):
                for count in (0, 2):
                    add(
                        {
                            "name": f"schema-{fixture['name']}-{fmt}-{method}-{count}",
                            "operation": method,
                            "format": fmt,
                            "schema": fixture["value"],
                            "texts": [clean] * count,
                        },
                        error("schema must be an object or boolean"),
                    )
            for repair in (True, False):
                add(
                    {
                        "name": f"schema-{fixture['name']}-{fmt}-generate-{str(repair).lower()}",
                        "operation": "generate",
                        "format": fmt,
                        "schema": fixture["value"],
                        "prompt": "data",
                        "repair": repair,
                        "generated_text": clean,
                    },
                    error("schema must be an object or boolean"),
                )
    for fixture in fixtures["valid_schemas"]:
        for fmt in fixtures["formats"]:
            text = "" if fmt == "toml" else "{}"
            for style in ("guard", "top"):
                add(
                    {
                        "name": f"schema-valid-{fixture['name']}-{fmt}-{style}",
                        "operation": "validate",
                        "style": style,
                        "format": fmt,
                        "schema": fixture["value"],
                        "text": text,
                    },
                    {
                        "valid": fixture["valid"],
                        "data": {},
                        "parse_failure": False,
                        "original_text": text,
                        "format": fmt,
                    },
                )
            for repair in (True, False):
                add(
                    {
                        "name": (
                            f"schema-valid-{fixture['name']}-{fmt}-generate-{str(repair).lower()}"
                        ),
                        "operation": "generate",
                        "format": fmt,
                        "schema": fixture["value"],
                        "prompt": "data",
                        "repair": repair,
                        "generated_text": text,
                    },
                    {"valid": fixture["valid"], "generated": 1, "observed": 1},
                )
    for group, valid in (("invalid_schemas", False), ("valid_schemas", True)):
        for fixture in fixtures[group]:
            add(
                {
                    "name": f"invalidate-{fixture['name']}",
                    "operation": "invalidate_schema",
                    "format": "json",
                    "schema": fixture["value"],
                },
                {"invalidated": True} if valid else error("schema must be an object or boolean"),
            )
    return cases


async def run_input_case(case: dict, *, asynchronous: bool = False) -> dict:
    result = {"error": None, "error_type": None, "processed": 0, "generated": 0, "observed": 0}

    class TrackedGuard(OutputGuard):
        def validate(self, *args, **kwargs):
            result["processed"] += 1
            return super().validate(*args, **kwargs)

        def repair(self, *args, **kwargs):
            result["processed"] += 1
            return super().repair(*args, **kwargs)

    def generate(prompt, context):
        result["generated"] += 1
        return case.get("generated_text", "{}")

    def observe(attempt):
        result["observed"] += 1

    try:
        op, fmt = case["operation"], case["format"]
        schema = case.get("schema", True)
        if op == "invalidate_schema":
            assert og.invalidate_schema(schema) is None
            result["invalidated"] = True
        elif op == "generate":
            options = dict(
                prompt=case["prompt"],
                schema=schema,
                format=fmt,
                generate=generate,
                on_attempt=observe,
                max_retries=0,
                repair=case["repair"],
            )
            generated = (
                await og.guarded_generate_async(**options)
                if asynchronous
                else og.guarded_generate(**options)
            )
            result["valid"] = generated.valid
        elif op in BATCH_METHODS:
            guard = TrackedGuard(format=fmt)
            if op == "repair_batch":
                batch = og.repair_batch(case["texts"], guard=guard)
            else:
                batch = og.validate_batch(
                    case["texts"], schema, guard=guard, repair=op == "validate_repair_batch"
                )
            result.update(
                texts=[item.input for item in batch.results],
                total=batch.summary.total,
                valid=batch.summary.valid,
                formats=batch.summary.formats,
            )
            if op != "repair_batch":
                result["data"] = [item.data for item in batch.results]
        else:
            target = og if case["style"] == "top" else OutputGuard()
            text = case["text"]
            if op in {"validate", "validate_and_repair"}:
                validated = getattr(target, op)(text, schema, format=fmt)
                result.update(
                    valid=validated.valid,
                    data=validated.data,
                    parse_failure=validated.parse_error is not None,
                    original_text=validated.original_text,
                    format=validated.format,
                )
            elif op == "parse":
                result["data"] = target.parse(text, schema, format=fmt)
            elif op.startswith("repair"):
                if op == "repair_report":
                    repaired, details = target.repair(text, format=fmt, report=True)
                    result.update(
                        report_success=details.success, report_original=details.original_text
                    )
                else:
                    repaired = target.repair(text, format=fmt)
                result.update(
                    repaired=repaired.repaired,
                    text=repaired.text,
                    parse_failure=repaired.parse_error is not None,
                    format=repaired.format,
                )
            else:
                history = op != "retry_prompt_no_history"
                prompt = target.retry_prompt(
                    text, schema, [], format=fmt, include_message_history=history
                )
                result.update(
                    history="\nOriginal output:\n" in prompt,
                    contains_text=text in prompt if history else None,
                )
    except TypeError as error:
        result.update(error=str(error), error_type="TypeError")
    return {"name": case["name"], **result}


def check_input_cases(cases: list[dict], *, asynchronous: bool) -> list[dict]:
    from benchmarks.comparison import assert_json_equal

    async def run():
        results = []
        for case in cases:
            result = await run_input_case(case, asynchronous=asynchronous)
            assert_json_equal(result, {"name": case["name"], **case["expected"]}, case["name"])
            results.append(result)
        return results

    return asyncio.run(run())
