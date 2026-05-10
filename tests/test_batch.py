import dataclasses
import json
from pathlib import Path

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
