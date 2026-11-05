"""Shared guarded-generation outcomes, error hierarchy, and callback ownership."""

import asyncio
import json
from pathlib import Path

import outputguard as og
from benchmarks.comparison import assert_json_equal

CASES_PATH = Path(__file__).with_name("generation_cases.json")


def generation_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def run_generation_case(case: dict, *, throwing: bool = False, asynchronous: bool = False) -> dict:
    observed = []
    generated = []
    expected = case["expected"]
    prompt = "Return structured data"

    def generate(current_prompt, context):
        index = len(generated)
        previous = expected["attempts"][index - 1] if index else None
        actual_context = {
            "attempt": context.attempt,
            "prompt_matches": context.prompt == current_prompt,
            "previous_text": context.previous_text,
            "previous_result_matches": context.previous_result
            is (observed[-1].result if observed else None),
            "initial_prompt": current_prompt == prompt,
            "history_present": "Original output:" in current_prompt,
        }
        assert_json_equal(
            actual_context,
            {
                "attempt": index,
                "prompt_matches": True,
                "previous_text": (previous["repaired_text"] or previous["raw_text"])
                if previous
                else None,
                "previous_result_matches": True,
                "initial_prompt": index == 0,
                "history_present": bool(index) and case.get("include_message_history", True),
            },
            f"{case['name']} context {index}",
        )
        generated.append(index)
        return case["responses"][index]

    def observe(attempt):
        observed.append(attempt)

    async def async_generate(*args):
        return generate(*args)

    async def async_observe(attempt):
        observe(attempt)

    options = dict(
        prompt=prompt,
        schema=case["schema"],
        format=case["format"],
        max_retries=case["max_retries"],
        repair=case["repair"],
        include_message_history=case.get("include_message_history", True),
        throw_on_failure=throwing,
    )
    caught = None
    try:
        result = (
            asyncio.run(
                og.guarded_generate_async(
                    **options, generate=async_generate, on_attempt=async_observe
                )
            )
            if asynchronous
            else og.guarded_generate(**options, generate=generate, on_attempt=observe)
        )
    except og.OutputGuardError as error:
        if not isinstance(error, og.GuardedGenerationError):
            raise
        caught = error
        result = error.result

    should_throw = throwing and not expected["valid"]
    assert_json_equal(caught is not None, should_throw, f"{case['name']} throwing policy")
    if caught is not None:
        assert_json_equal(
            str(caught),
            f"Failed to generate valid {case['format']} output after "
            f"{len(expected['attempts'])} attempt(s)",
            f"{case['name']} error message",
        )
    assert_json_equal(
        [item is seen for item, seen in zip(result.attempts, observed, strict=True)],
        [True] * len(expected["attempts"]),
        f"{case['name']} observer attempt identity",
    )
    actual = {
        "valid": result.valid,
        "data": result.data,
        "text": result.text,
        "repaired": result.repaired,
        "strategies": result.strategies_applied,
        "exhausted": result.exhausted,
        "format": result.format,
        "error_paths": [error.path for error in result.errors],
        "attempts": [
            {
                "raw_text": attempt.raw_text,
                "valid": attempt.result.valid,
                "data": attempt.result.data,
                "repaired": attempt.result.repaired,
                "repaired_text": attempt.result.repaired_text,
                "strategies": attempt.result.strategies_applied,
                "parse_failure": attempt.result.parse_error is not None,
                "error_paths": [error.path for error in attempt.result.errors],
            }
            for attempt in result.attempts
        ],
        "provider_calls": len(generated),
        "observer_calls": len(observed),
    }
    assert_json_equal(actual, expected, case["name"])
    return {"name": case["name"], "thrown": caught is not None, **actual}


def check_generation_cases(
    cases: list[dict], *, throwing: bool = False, asynchronous: bool = False
) -> list[dict]:
    return [
        run_generation_case(case, throwing=throwing, asynchronous=asynchronous) for case in cases
    ]
