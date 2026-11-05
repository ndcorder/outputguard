"""Parsing, repair and schema failure must remain distinct across public APIs."""

import asyncio
import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import outputguard
from outputguard.cli import cli
from outputguard.exceptions import ParseError, SchemaValidationError

NULL_CASES = [("json", "null"), ("yaml", "null"), ("python", "None")]
REPAIR_CASES = [
    ("json", '```json\n{"age": "old"}\n```', '{"age": "old"}'),
    ("yaml", "```yaml\nage: old\n```", "age: old"),
    ("toml", '```toml\nage = "old"\n```', 'age = "old"'),
    ("python", "```python\n{'age': 'old'}\n```", "{'age': 'old'}"),
]
SCHEMA = {"type": "object", "properties": {"age": {"type": "integer"}}}


@pytest.mark.parametrize(("format", "text"), NULL_CASES)
def test_parse_returns_null_when_schema_accepts_it(format, text):
    assert outputguard.parse(text, {"type": "null"}, format=format) is None
    result = outputguard.validate(text, {"type": "null"}, format=format)
    assert result.valid
    assert result.parse_error is None


@pytest.mark.parametrize(("format", "text"), NULL_CASES)
def test_null_schema_failure_is_not_a_parse_failure(format, text):
    result = outputguard.validate(text, SCHEMA, format=format)
    assert not result.valid
    assert result.parse_error is None
    with pytest.raises(SchemaValidationError) as exc:
        outputguard.parse(text, SCHEMA, format=format)
    assert exc.value.data is None
    batch = outputguard.validate_batch([text], SCHEMA, format=format)
    assert batch.summary.parse_failures == 0
    assert batch.summary.schema_failures == 1


@pytest.mark.parametrize(("format", "text", "repaired_text"), REPAIR_CASES)
def test_repaired_schema_failure_preserves_data_text_and_errors(format, text, repaired_text):
    result = outputguard.validate_and_repair(text, SCHEMA, format=format)
    assert not result.valid
    assert result.repaired
    assert result.data == {"age": "old"}
    assert result.original_text == text
    assert result.repaired_text == repaired_text
    assert result.strategies_applied == ["strip_fences"]
    assert result.parse_error is None
    assert result.errors[0].path == "$.age"
    with pytest.raises(SchemaValidationError) as exc:
        outputguard.parse(text, SCHEMA, format=format)
    assert exc.value.data == result.data


def test_parse_failure_exposes_parser_diagnostic():
    result = outputguard.validate("not json", SCHEMA)
    assert result.parse_error == result.errors[0].message
    with pytest.raises(ParseError) as exc:
        outputguard.parse("not json", SCHEMA)
    assert exc.value.parse_error == result.parse_error


@pytest.mark.parametrize("text", ['{"age":"old"}', "not json"])
def test_deterministic_repair_stops_when_it_cannot_make_progress(text):
    from outputguard.repairer import repair

    with patch("outputguard.guard._repairer.repair", wraps=repair) as repairing:
        result = outputguard.validate_and_repair(text, SCHEMA)
    assert not result.valid
    assert repairing.call_count == (1 if result.parse_error else 0)


def test_repaired_null_and_batch_failure_counts():
    assert outputguard.parse("```json\nnull\n```", {"type": "null"}) is None
    batch = outputguard.validate_batch(
        ["null", "```json\nnull\n```", "not json", '{"age": 42}'], SCHEMA, repair=True
    )
    assert batch.summary.valid == 1
    assert batch.summary.repaired == 1
    assert batch.summary.parse_failures == 1
    assert batch.summary.schema_failures == 2
    assert batch.summary.strategy_counts == {"strip_fences": 1}


def test_zero_repair_attempts_preserves_original_parse_failure():
    text = '```json\n{"age": "old"}\n```'
    result = outputguard.OutputGuard(max_repair_attempts=0).validate_and_repair(text, SCHEMA)
    assert not result.valid
    assert not result.repaired
    assert result.original_text == text
    assert result.repaired_text == ""
    assert result.parse_error is not None


@pytest.mark.parametrize("async_mode", [False, True])
def test_generation_retries_with_repaired_text_and_schema_feedback(async_mode):
    prompts = []
    contexts = []

    def generate(prompt, context):
        prompts.append(prompt)
        contexts.append(context)
        return '```json\n{"age": "old"}\n```' if context.attempt == 0 else '{"age":42}'

    async def async_generate(prompt, context):
        return generate(prompt, context)

    options = dict(prompt="Return an age", schema=SCHEMA, max_retries=1)
    if async_mode:
        result = asyncio.run(outputguard.guarded_generate_async(generate=async_generate, **options))
    else:
        result = outputguard.guarded_generate(generate=generate, **options)
    assert result.valid
    assert result.repaired
    assert result.strategies_applied == ["strip_fences"]
    assert contexts[1].previous_text == '{"age": "old"}'
    assert contexts[1].previous_result.errors[0].path == "$.age"
    assert "$.age" in prompts[1]
    assert "```json" not in prompts[1]


def test_cli_serializes_repaired_schema_failure(tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(SCHEMA))
    result = CliRunner().invoke(
        cli,
        ["validate", "-", "-s", str(schema_path), "--repair", "-f", "json"],
        input='```json\n{"age": "old"}\n```',
    )
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["repaired"]
    assert payload["parse_error"] is None
    assert payload["data"] == {"age": "old"}
    assert payload["errors"][0]["path"] == "$.age"
