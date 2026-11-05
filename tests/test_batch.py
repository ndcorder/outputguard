import dataclasses
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

import outputguard
from outputguard.cli import cli

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


def test_validate_batch_summarizes_validity_repairs_and_failures() -> None:
    batch = outputguard.validate_batch(
        [
            '{"name": "Alice", "age": 30}',
            '```json\n{"name": "Bob", "age": 31}\n```',
            '{"name": "Carol"}',
            "not structured output",
        ],
        SIMPLE_SCHEMA,
        repair=True,
    )

    assert dataclasses.asdict(batch.summary) == {
        "total": 4,
        "valid": 2,
        "invalid": 2,
        "repaired": 1,
        "parse_failures": 1,
        "schema_failures": 1,
        "success_rate": 0.5,
        "strategy_counts": {"strip_fences": 1},
        "formats": {"json": 4},
    }
    assert [result.index for result in batch.results] == [0, 1, 2, 3]
    assert batch.results[1].repaired_text == '{"name": "Bob", "age": 31}'
    assert any("age" in error.message for error in batch.results[2].errors)


def test_validate_batch_handles_auto_detected_mixed_formats() -> None:
    batch = outputguard.validate_batch(
        [
            '{"name": "Alice", "age": 30}',
            "name: Bob\nage: 31\n",
            "{'name': 'Carol', 'age': 32}",
        ],
        SIMPLE_SCHEMA,
        format="auto",
    )

    assert batch.summary.valid == 3
    assert batch.summary.invalid == 0
    assert batch.summary.formats == {"auto": 3}
    assert [result.data for result in batch.results] == [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 31},
        {"name": "Carol", "age": 32},
    ]


def test_repair_batch_summarizes_strategy_counts() -> None:
    batch = outputguard.repair_batch(
        [
            '{"name": "Alice", "age": 30}',
            '```json\n{"name": "Bob", "age": 31}\n```',
            "{name:'Carol', age:32,}",
            "not structured output",
        ]
    )

    assert batch.summary.total == 4
    assert batch.summary.valid == 3
    assert batch.summary.invalid == 1
    assert batch.summary.repaired == 2
    assert batch.summary.strategy_counts["strip_fences"] == 1
    assert batch.summary.strategy_counts["fix_commas"] == 1
    assert batch.summary.strategy_counts["fix_quotes"] == 1
    assert batch.summary.strategy_counts["fix_keys"] == 1
    assert batch.results[0].index == 0
    assert batch.results[3].parse_error is not None


@pytest.mark.parametrize("repair", [False, True])
def test_validate_batch_inherits_guard_format(repair):
    guard = outputguard.OutputGuard(format="yaml")
    text = "name: Alice\nage: 30"
    if repair:
        text = f"```yaml\n{text}\n```"
    batch = outputguard.validate_batch([text], SIMPLE_SCHEMA, guard=guard, repair=repair)
    assert batch.summary.valid == 1
    assert batch.summary.formats == {"yaml": 1}
    assert batch.results[0].repaired is repair


def test_repair_batch_inherits_guard_format():
    text = "```yaml\nname: Alice\nage: 30\n```"
    batch = outputguard.repair_batch([text], guard=outputguard.OutputGuard(format="yaml"))
    assert batch.summary.valid == 1
    assert batch.summary.formats == {"yaml": 1}
    assert batch.results[0].text == "name: Alice\nage: 30"


@pytest.mark.parametrize("repair", [False, True])
def test_validate_batch_format_override_does_not_change_guard(repair):
    guard = outputguard.OutputGuard(format="toml")
    batch = outputguard.validate_batch(
        ['{"name":"Alice","age":30}'], SIMPLE_SCHEMA, format="json", guard=guard, repair=repair
    )
    assert batch.summary.valid == 1
    assert batch.summary.formats == {"json": 1}
    assert guard.format == "toml"


def test_repair_batch_format_override_does_not_change_guard():
    guard = outputguard.OutputGuard(format="toml")
    batch = outputguard.repair_batch(['{"age":30,}'], format="json", guard=guard)
    assert batch.summary.valid == 1
    assert batch.summary.formats == {"json": 1}
    assert batch.results[0].text == '{"age":30}'
    assert guard.format == "toml"


@pytest.mark.parametrize(
    "valid,total,expected",
    [(1, 16, 0.063), (5, 16, 0.313), (9, 16, 0.563), (0, 16, 0.0), (16, 16, 1.0)],
)
def test_batch_success_rate_rounds_half_up(valid, total, expected):
    texts = ["1"] * valid + ["false"] * (total - valid)
    batch = outputguard.validate_batch(texts, {"type": "number"})
    assert batch.summary.success_rate == expected


def test_repair_batch_success_rate_rounds_half_up():
    batch = outputguard.repair_batch(["1"] + ["not json"] * 15)
    assert batch.summary.success_rate == 0.063


@pytest.mark.parametrize("operation", ["validate", "validate_repair", "repair"])
def test_batch_counts_arbitrary_custom_guard_metadata(operation, monkeypatch):
    names = [
        "__proto__",
        "constructor",
        "toString",
        "hasOwnProperty",
        "valueOf",
        "__defineGetter__",
    ]
    guard = outputguard.OutputGuard()

    def custom_result(text, *args, **kwargs):
        metadata = {"repaired": True, "strategies_applied": [text, text, "shared"], "format": text}
        if operation == "repair":
            return outputguard.RepairResult(text=text, **metadata)
        return outputguard.ValidationResult(valid=True, original_text=text, **metadata)

    method = {"validate": "validate", "validate_repair": "validate_and_repair", "repair": "repair"}[
        operation
    ]
    monkeypatch.setattr(guard, method, custom_result)
    batch = (
        outputguard.repair_batch(names, guard=guard)
        if operation == "repair"
        else outputguard.validate_batch(
            names, True, repair=operation == "validate_repair", guard=guard
        )
    )
    assert batch.summary.strategy_counts == {**dict.fromkeys(names, 2), "shared": len(names)}
    assert batch.summary.formats == dict.fromkeys(names, 1)
    assert batch.summary.valid == batch.summary.repaired == len(names)
    assert list(batch.summary.formats) == names
    assert [result.format for result in batch.results] == names


@pytest.mark.parametrize("operation", ["validate", "validate_repair", "repair"])
def test_batch_summarizes_final_shared_metadata(operation, monkeypatch):
    names = ["first", "second", "last"]
    strategies = []
    guard = outputguard.OutputGuard()

    def custom_result(text, *args, **kwargs):
        strategies.append(text)
        if operation == "repair":
            return outputguard.RepairResult(repaired=True, text=text, strategies_applied=strategies)
        return outputguard.ValidationResult(
            valid=True, repaired=True, strategies_applied=strategies
        )

    method = {"validate": "validate", "validate_repair": "validate_and_repair", "repair": "repair"}[
        operation
    ]
    monkeypatch.setattr(guard, method, custom_result)
    batch = (
        outputguard.repair_batch(names, guard=guard)
        if operation == "repair"
        else outputguard.validate_batch(
            names, True, repair=operation == "validate_repair", guard=guard
        )
    )
    assert all(result.strategies_applied is strategies for result in batch.results)
    assert strategies == names
    assert batch.summary.strategy_counts == dict.fromkeys(names, len(names))
    assert batch.summary.formats == {"json": len(names)}


def test_cli_batch_validates_json_array_of_outputs(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(SIMPLE_SCHEMA))
    input_path = tmp_path / "outputs.json"
    input_path.write_text(
        json.dumps(
            [
                '{"name": "Alice", "age": 30}',
                '```json\n{"name": "Bob", "age": 31}\n```',
                '{"name": "Carol"}',
            ]
        )
    )

    result = CliRunner().invoke(
        cli,
        [
            "batch",
            str(input_path),
            "-s",
            str(schema_path),
            "--repair",
            "-f",
            "json",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert (
        payload["summary"]
        | {
            "total": 3,
            "valid": 2,
            "invalid": 1,
            "repaired": 1,
        }
        == payload["summary"]
    )
    assert payload["results"][1]["repaired_text"] == '{"name": "Bob", "age": 31}'
