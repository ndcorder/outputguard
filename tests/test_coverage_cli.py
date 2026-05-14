"""Tests for uncovered lines in outputguard/cli.py.

Targets: _write_output file path (L57-58), _show_repair_details (L121, L132-145),
batch JSON format (L245), batch text format with stats (L254-265).
"""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from outputguard.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def schema_path():
    return str(Path(__file__).parent / "fixtures" / "simple_schema.json")


@pytest.fixture
def valid_json_file(tmp_path):
    f = tmp_path / "valid.json"
    f.write_text('{"name": "Alice", "age": 30}')
    return str(f)


@pytest.fixture
def invalid_json_file(tmp_path):
    f = tmp_path / "invalid.json"
    f.write_text('{"name": "Alice"}')
    return str(f)


@pytest.fixture
def repairable_json_file(tmp_path):
    f = tmp_path / "repairable.json"
    f.write_text('```json\n{"name": "Alice", "age": 30}\n```')
    return str(f)


# --- _write_output file path (L57-58) ---


def test_validate_json_format_writes_to_file(runner, schema_path, valid_json_file, tmp_path):
    """validate -f json -o FILE writes JSON result to the output file."""
    out = tmp_path / "result.json"
    result = runner.invoke(
        cli,
        ["validate", valid_json_file, "-s", schema_path, "-f", "json", "-o", str(out)],
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["valid"] is True


def test_validate_repair_writes_repaired_text_to_file(
    runner, schema_path, repairable_json_file, tmp_path
):
    """validate --repair -o FILE writes repaired text to the output file."""
    out = tmp_path / "repaired.json"
    result = runner.invoke(
        cli,
        [
            "validate",
            repairable_json_file,
            "-s",
            schema_path,
            "--repair",
            "-o",
            str(out),
        ],
    )
    assert result.exit_code == 0
    data = json.loads(out.read_text())
    assert data["name"] == "Alice"
    assert data["age"] == 30


# --- _show_repair_details verbose path (L121, L132-139) ---


def test_validate_repair_verbose_shows_strategy_details(runner, schema_path, repairable_json_file):
    """validate --repair --verbose prints strategy details and confidence."""
    result = runner.invoke(
        cli,
        [
            "validate",
            repairable_json_file,
            "-s",
            schema_path,
            "--repair",
            "--verbose",
        ],
    )
    assert result.exit_code == 0
    assert "Confidence" in result.output


# --- _show_repair_details diff path (L140-145) ---


def test_validate_repair_diff_shows_diff(runner, schema_path, repairable_json_file):
    """validate --repair --diff prints a diff of the repair."""
    result = runner.invoke(
        cli,
        [
            "validate",
            repairable_json_file,
            "-s",
            schema_path,
            "--repair",
            "--diff",
        ],
    )
    assert result.exit_code == 0
    assert "Diff" in result.output or "---" in result.output or "```" in result.output


# --- batch command JSON format (L245) ---


def test_batch_json_format(runner, schema_path, tmp_path):
    """batch -f json outputs JSON with batch results."""
    items = ['{"name": "Alice", "age": 30}', '{"name": "Bob", "age": 25}']
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(json.dumps(items))
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path, "-f", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "summary" in data


# --- batch command text format with mixed results (L254-265) ---


def test_batch_text_format_with_invalid_items(runner, schema_path, tmp_path):
    """batch (text) shows valid/invalid counts when some items fail."""
    items = [
        '{"name": "Alice", "age": 30}',
        '{"name": "Bob"}',  # missing required 'age'
    ]
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(json.dumps(items))
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path],
    )
    assert result.exit_code == 1
    assert "1/2 valid" in result.output
    assert "1 invalid" in result.output


def test_batch_text_format_with_repair(runner, schema_path, tmp_path):
    """batch --repair (text) shows repaired count and strategy names."""
    items = [
        '```json\n{"name": "Alice", "age": 30}\n```',  # needs strip_fences
        '{"name": "Bob", "age": 25}',  # already valid
    ]
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(json.dumps(items))
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path, "--repair"],
    )
    assert result.exit_code == 0
    assert "2/2 valid" in result.output
    assert "Repaired" in result.output


def test_batch_text_format_all_valid(runner, schema_path, tmp_path):
    """batch (text) shows green checkmark when all items are valid."""
    items = ['{"name": "Alice", "age": 30}', '{"name": "Bob", "age": 25}']
    batch_file = tmp_path / "batch.json"
    batch_file.write_text(json.dumps(items))
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path],
    )
    assert result.exit_code == 0
    assert "2/2 valid" in result.output


# --- repair command JSON format (L192) ---


def test_repair_json_format(runner, repairable_json_file):
    """repair -f json outputs the repair result as JSON."""
    result = runner.invoke(
        cli,
        ["repair", repairable_json_file, "-f", "json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["repaired"] is True
    assert "strip_fences" in data["strategies_applied"]


# --- repair command "already valid" text path (L212-214) ---


def test_repair_already_valid(runner, valid_json_file):
    """repair on already-valid input shows 'Already valid' message."""
    result = runner.invoke(
        cli,
        ["repair", valid_json_file],
    )
    assert result.exit_code == 0
    assert "Already valid" in result.output


# --- repair command "could not repair" path (L210-211) ---


def test_repair_unrepairable(runner, tmp_path):
    """repair on completely broken input shows 'Could not repair'."""
    f = tmp_path / "broken.json"
    f.write_text("this is not json or any structured format at all {{{{")
    result = runner.invoke(
        cli,
        ["repair", str(f)],
    )
    assert result.exit_code == 1
    assert "Could not repair" in result.output


# --- batch command invalid input validation (L245) ---


def test_batch_rejects_non_array_input(runner, schema_path, tmp_path):
    """batch errors when input is not a JSON array of strings."""
    batch_file = tmp_path / "bad_batch.json"
    batch_file.write_text('{"not": "an array"}')
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path],
    )
    assert result.exit_code != 0
    assert "JSON array of strings" in result.output


def test_batch_rejects_non_string_items(runner, schema_path, tmp_path):
    """batch errors when array contains non-string items."""
    batch_file = tmp_path / "bad_batch.json"
    batch_file.write_text("[1, 2, 3]")
    result = runner.invoke(
        cli,
        ["batch", str(batch_file), "-s", schema_path],
    )
    assert result.exit_code != 0
    assert "JSON array of strings" in result.output


# --- _show_repair_details early return when not repaired (L133) ---


def test_show_repair_details_not_repaired(runner, schema_path, valid_json_file):
    """_show_repair_details returns early when result is not repaired.

    We test this indirectly by calling validate --repair --verbose on valid
    input that needs no repair — _show_repair_details gets called but the
    result.repaired is False so it hits the early return.
    """
    # Actually, validate only calls _show_repair_details when
    # result.valid AND result.repaired, so we test the function directly.
    from outputguard.cli import _show_repair_details
    from outputguard.models import ValidationResult

    non_repaired = ValidationResult(
        valid=True,
        data={"name": "Alice", "age": 30},
        errors=[],
        repaired=False,
        strategies_applied=[],
        original_text='{"name": "Alice", "age": 30}',
        repaired_text=None,
        format="json",
    )
    # Should return immediately without raising
    _show_repair_details('{"name": "Alice", "age": 30}', non_repaired, True, "json")
