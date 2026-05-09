import json

import pytest
from click.testing import CliRunner
from pathlib import Path

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


def test_validate_valid(runner, schema_path, valid_json_file):
    result = runner.invoke(cli, ["validate", valid_json_file, "-s", schema_path])
    assert result.exit_code == 0


def test_validate_invalid(runner, schema_path, invalid_json_file):
    result = runner.invoke(cli, ["validate", invalid_json_file, "-s", schema_path])
    assert result.exit_code == 1


def test_validate_repair(runner, schema_path, repairable_json_file):
    result = runner.invoke(cli, ["validate", repairable_json_file, "-s", schema_path, "--repair"])
    assert result.exit_code == 0


def test_repair_command(runner, tmp_path):
    f = tmp_path / "fenced.json"
    f.write_text('```json\n{"a": 1}\n```')
    result = runner.invoke(cli, ["repair", str(f)])
    assert result.exit_code == 0


def test_strategies_command(runner):
    result = runner.invoke(cli, ["strategies"])
    assert result.exit_code == 0
    assert "strip_fences" in result.output


def test_retry_prompt_command(runner, schema_path, invalid_json_file):
    result = runner.invoke(cli, ["retry-prompt", invalid_json_file, "-s", schema_path])
    assert result.exit_code == 0
    assert "error" in result.output.lower() or "Error" in result.output


def test_json_format(runner, schema_path, valid_json_file):
    result = runner.invoke(cli, ["validate", valid_json_file, "-s", schema_path, "-f", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["valid"] is True


def test_stdin_input(runner, schema_path):
    result = runner.invoke(cli, ["validate", "-", "-s", schema_path], input='{"name": "Alice", "age": 30}')
    assert result.exit_code == 0


def test_quiet_mode(runner, schema_path, valid_json_file):
    result = runner.invoke(cli, ["validate", valid_json_file, "-s", schema_path, "-q"])
    assert result.exit_code == 0
    assert result.output.strip() == ""
