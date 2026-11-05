import asyncio
import json
from pathlib import Path

import pytest

import outputguard as og
from outputguard.repairer import repair
from outputguard.strategies import ALL_STRATEGIES, get_strategies, get_strategy

CASES = json.loads((Path(__file__).parents[1] / "benchmarks/configuration_cases.json").read_text())[
    "strategy_selections"
]


def selection_error(case):
    return TypeError if case.get("error") == "strategy_type" else ValueError


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_selection_and_introspection(case):
    selected = case["value"]
    if not case["valid"]:
        for call in (lambda: get_strategies(selected), lambda: og.OutputGuard(strategies=selected)):
            with pytest.raises(selection_error(case), match="[Ss]trateg"):
                call()
        return
    assert [name for name, _ in get_strategies(selected)] == case["selected"]
    guard = og.OutputGuard(strategies=selected)
    assert guard.strategy_names == case["selected"]
    names = guard.strategy_names
    names.clear()
    assert guard.strategy_names == case["selected"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
@pytest.mark.parametrize("text", ['{"value":1}', '{"value":1,}'])
@pytest.mark.parametrize("report", [False, True])
def test_low_level_repair_checks_selection_even_for_valid_input(case, text, report):
    if not case["valid"]:
        with pytest.raises(selection_error(case), match="[Ss]trateg"):
            repair(text, case["value"], report=report)
        return
    result = repair(text, case["value"], report=report)
    if report:
        result, details = result
        assert details.success == (result.parse_error is None)
        assert details.strategies_tried == (case["selected"] if text.endswith(",}") else [])
    expected_fix = text.endswith(",}") and "fix_commas" in case["selected"]
    assert result.repaired == expected_fix
    assert result.text == ('{"value":1}' if expected_fix else text)


def test_constructor_copies_sequence_and_preserves_fixed_order():
    names = ["fix_commas", "strip_fences", "fix_commas"]
    guard = og.OutputGuard(strategies=names)
    names.append("fix_quotes")
    assert guard.strategy_names == ["strip_fences", "fix_commas"]
    assert not guard.repair("{'value':1}").repaired
    assert guard.repair('```json\n{"value":1,}\n```').repaired
    assert og.OutputGuard(strategies=tuple(names)).strategy_names == [
        "strip_fences",
        "fix_commas",
        "fix_quotes",
    ]


@pytest.mark.parametrize(
    "value", [b"fix_commas", bytearray(b"fix_commas"), {"fix_commas"}, iter(["fix_commas"])]
)
def test_non_sequence_selection_is_not_consumed_or_coerced(value):
    with pytest.raises(TypeError, match="sequence"):
        get_strategies(value)


@pytest.mark.parametrize("value", [None, False, 1, [], {}])
def test_single_strategy_name_requires_string(value):
    with pytest.raises(TypeError, match="strategy name"):
        get_strategy(value)


@pytest.mark.parametrize(
    "operation",
    [
        "repair",
        "validate_and_repair",
        "parse",
        "repair_batch",
        "validate_batch",
        "generate",
        "generate_async",
    ],
)
def test_mutated_configuration_is_checked_before_work(operation):
    guard = og.OutputGuard(strategies=["fix_commas"], max_repair_attempts=0)
    guard.strategies.append("typo")
    generated = []

    def generate(prompt, context):
        generated.append(context.attempt)
        return "{}"

    with pytest.raises(ValueError, match="Unknown strategy"):
        if operation == "repair_batch":
            og.repair_batch([], guard=guard)
        elif operation == "validate_batch":
            og.validate_batch([], True, guard=guard, repair=True)
        elif operation.startswith("generate"):
            options = dict(prompt="data", schema=True, guard=guard, generate=generate)
            if operation == "generate_async":
                asyncio.run(og.guarded_generate_async(**options))
            else:
                og.guarded_generate(**options)
        elif operation == "repair":
            guard.repair("{}")
        else:
            getattr(guard, operation)("{}", True)
    assert generated == []
    assert guard.validate("{}", True).valid
    assert og.guarded_generate(
        prompt="data", schema=True, guard=guard, generate=generate, repair=False
    ).valid


def test_registry_extension_and_removal_are_visible(monkeypatch):
    import outputguard.strategies as registry

    def custom(text):
        return text.replace("CUSTOM", "1")

    monkeypatch.setattr(registry, "ALL_STRATEGIES", [*ALL_STRATEGIES, ("custom", custom)])
    guard = og.OutputGuard(strategies=["custom"])
    assert guard.strategy_names == ["custom"]
    assert guard.repair('{"value":CUSTOM}').text == '{"value":1}'
    registry.ALL_STRATEGIES.pop()
    with pytest.raises(ValueError, match="Unknown strategy"):
        og.guarded_generate(
            prompt="data",
            schema=True,
            guard=guard,
            generate=lambda *_: pytest.fail("provider was called"),
        )
