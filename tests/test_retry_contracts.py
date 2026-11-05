import asyncio
import json

import pytest

import outputguard as og
from benchmarks.run import CASES_PATH
from outputguard.models import ValidationError
from outputguard.retry import retry_prompt

CASES = [
    case
    for case in json.loads(CASES_PATH.read_text())
    if case["name"].startswith(("retry_history_", "retry_summary_"))
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("style", ["raw", "guard", "top"])
def test_exact_retry_prompts(case, style):
    method = (
        retry_prompt
        if style == "raw"
        else og.OutputGuard(format="yaml").retry_prompt
        if style == "guard"
        else og.retry_prompt
    )
    errors = [ValidationError(**error) for error in case["errors"]]
    actual = method(
        case["text"],
        case["schema"],
        errors,
        format=case["format"],
        include_message_history=case["include_message_history"],
    )
    assert actual == case["expected"]["prompt"]


@pytest.mark.parametrize("history", [True, False])
@pytest.mark.parametrize("repair", [True, False])
@pytest.mark.parametrize("asynchronous", [True, False])
def test_generation_passes_unicode_feedback_to_next_provider_call(history, repair, asynchronous):
    first = json.dumps({"value": "a" * 239 + "😀" * 300 + "b" * 251}, ensure_ascii=False)
    contexts, observed = [], []

    def generate(prompt, context):
        contexts.append(context)
        return first if context.attempt == 0 else '{"value":1}'

    async def generate_async(prompt, context):
        return generate(prompt, context)

    options = dict(
        prompt="Return data",
        schema={"type": "object", "properties": {"value": {"type": "integer"}}},
        max_retries=1,
        repair=repair,
        include_message_history=history,
        on_attempt=observed.append,
    )
    result = (
        asyncio.run(og.guarded_generate_async(**options, generate=generate_async))
        if asynchronous
        else og.guarded_generate(**options, generate=generate)
    )
    assert result.valid and result.data == {"value": 1}
    assert len(contexts) == len(observed) == len(result.attempts) == 2
    assert contexts[0].prompt == "Return data"
    second = contexts[1]
    assert second.previous_text == first
    assert second.previous_result is observed[0].result
    assert not second.previous_result.valid and second.previous_result.parse_error is None
    assert second.previous_result.errors[0].path == "$.value"
    assert result.attempts[1].prompt == second.prompt
    if history:
        kept = second.prompt.split("\nOriginal output:\n")[1].split("\n\nReturn ONLY")[0]
        assert kept == first[:250] + "\n...\n" + first[-250:]
    else:
        assert "Original output:" not in second.prompt
        assert "😀" not in second.prompt.split("\nThe expected schema requires:")[1]


def test_schema_summary_stops_at_depth_limit_for_a_direct_cycle():
    schema = {"type": ["object", "null"], "properties": {}}
    schema["properties"]["next"] = schema
    prompt = og.retry_prompt("{}", schema, [], include_message_history=False)
    summary = prompt.split("The expected schema requires:\n")[1].split("\n\nReturn ONLY")[0]
    assert summary.splitlines() == [
        "- A root object or null with properties: next (object or null)",
        "  - For object values, contains properties: next (object or null)",
        "    - For object values, contains properties: next (object or null)",
    ]
    assert schema["properties"]["next"] is schema


def test_numeric_looking_property_names_do_not_require_unbounded_integer_conversion():
    name = "9" * 10000
    schema = {"properties": {name: True, "1": False, "0": True}}
    prompt = og.retry_prompt("{}", schema, [], include_message_history=False)
    assert f"- A root any with properties: 0 (any), 1 (forbidden), {name} (any)" in prompt
    assert list(schema["properties"]) == [name, "1", "0"]
