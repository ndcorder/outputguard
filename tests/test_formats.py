import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

import outputguard
from outputguard import OutputGuard
from outputguard.cli import cli
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.repairer import repair as raw_repair


@dataclass(frozen=True)
class FormatCase:
    name: str
    valid_object: str
    invalid_object: str
    repairable_object: str
    garbage: str
    expected_repaired_text: str


FORMAT_CASES = [
    FormatCase(
        name="json",
        valid_object='{"name": "Alice", "age": 30}',
        invalid_object='{"name": "Alice"}',
        repairable_object='```json\n{"name": "Alice", "age": 30}\n```',
        garbage="not json at all",
        expected_repaired_text='{"name": "Alice", "age": 30}',
    ),
    FormatCase(
        name="yaml",
        valid_object="name: Alice\nage: 30\n",
        invalid_object="name: Alice\n",
        repairable_object="```yaml\nname: Alice\nage: 30\n```",
        garbage="name: [unterminated\n",
        expected_repaired_text="name: Alice\nage: 30",
    ),
    FormatCase(
        name="toml",
        valid_object='name = "Alice"\nage = 30\n',
        invalid_object='name = "Alice"\n',
        repairable_object='```toml\nname = "Alice"\nage = 30\n```',
        garbage='name = "Alice"\nage = \n',
        expected_repaired_text='name = "Alice"\nage = 30',
    ),
    FormatCase(
        name="python",
        valid_object="{'name': 'Alice', 'age': 30}",
        invalid_object="{'name': 'Alice'}",
        repairable_object="```python\n{'name': 'Alice', 'age': 30}\n```",
        garbage="{'name': 'Alice', 'age': }",
        expected_repaired_text="{'name': 'Alice', 'age': 30}",
    ),
]


AUTO_CASES = [
    pytest.param("auto", FORMAT_CASES[0].valid_object, id="auto-json"),
    pytest.param("auto", FORMAT_CASES[1].valid_object, id="auto-yaml"),
    pytest.param("auto", FORMAT_CASES[2].valid_object, id="auto-toml"),
    pytest.param("auto", FORMAT_CASES[3].valid_object, id="auto-python"),
    pytest.param("forced-json-off", FORMAT_CASES[1].valid_object, id="forced-json-off-yaml"),
    pytest.param("forced-json-off", FORMAT_CASES[3].valid_object, id="forced-json-off-python"),
]

ALIAS_CASES = [
    pytest.param("yml", FORMAT_CASES[1].valid_object, id="yml"),
    pytest.param("python-literal", FORMAT_CASES[3].valid_object, id="python-literal"),
    pytest.param("literal", FORMAT_CASES[3].valid_object, id="literal"),
]


SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


@pytest.fixture(params=FORMAT_CASES, ids=lambda case: case.name)
def format_case(request: pytest.FixtureRequest) -> FormatCase:
    return request.param


def test_validate_accepts_supported_format(format_case: FormatCase) -> None:
    result = outputguard.validate(format_case.valid_object, SIMPLE_SCHEMA, format=format_case.name)

    assert result.valid is True
    assert result.errors == []
    assert result.data == {"name": "Alice", "age": 30}
    assert result.format == format_case.name


def test_validate_reports_schema_errors_for_supported_format(format_case: FormatCase) -> None:
    result = outputguard.validate(
        format_case.invalid_object, SIMPLE_SCHEMA, format=format_case.name
    )

    assert result.valid is False
    assert result.data == {"name": "Alice"}
    assert any("age" in error.message for error in result.errors)
    assert result.format == format_case.name


def test_validate_reports_parse_errors_for_supported_format(format_case: FormatCase) -> None:
    result = outputguard.validate(format_case.garbage, SIMPLE_SCHEMA, format=format_case.name)

    assert result.valid is False
    assert result.data is None
    assert result.errors[0].path == "$"
    assert result.format == format_case.name


def test_repair_handles_fenced_supported_format(format_case: FormatCase) -> None:
    result = outputguard.repair(format_case.repairable_object, format=format_case.name)

    assert result.repaired is True
    assert result.text == format_case.expected_repaired_text
    assert "strip_fences" in result.strategies_applied
    assert result.format == format_case.name


def test_repair_report_handles_supported_format(format_case: FormatCase) -> None:
    result, report = raw_repair(format_case.repairable_object, report=True, format=format_case.name)

    assert result.repaired is True
    assert report.success is True
    assert report.final_text == format_case.expected_repaired_text
    assert report.format == format_case.name
    assert "strip_fences" in report.strategies_applied


def test_validate_and_repair_handles_supported_format(format_case: FormatCase) -> None:
    result = outputguard.validate_and_repair(
        format_case.repairable_object, SIMPLE_SCHEMA, format=format_case.name
    )

    assert result.valid is True
    assert result.repaired is True
    assert result.data == {"name": "Alice", "age": 30}
    assert result.repaired_text == format_case.expected_repaired_text
    assert result.format == format_case.name


def test_parse_returns_data_for_supported_format(format_case: FormatCase) -> None:
    data = outputguard.parse(format_case.valid_object, SIMPLE_SCHEMA, format=format_case.name)

    assert data == {"name": "Alice", "age": 30}


def test_parse_raises_parse_error_for_supported_format(format_case: FormatCase) -> None:
    with pytest.raises(ParseError) as exc_info:
        outputguard.parse(format_case.garbage, SIMPLE_SCHEMA, format=format_case.name)

    assert exc_info.value.original_text == format_case.garbage
    assert exc_info.value.format == format_case.name


def test_parse_raises_schema_error_for_supported_format(format_case: FormatCase) -> None:
    with pytest.raises(SchemaValidationError) as exc_info:
        outputguard.parse(format_case.invalid_object, SIMPLE_SCHEMA, format=format_case.name)

    assert exc_info.value.data == {"name": "Alice"}
    assert exc_info.value.format == format_case.name


def test_output_guard_instance_default_format(format_case: FormatCase) -> None:
    guard = OutputGuard(format=format_case.name)

    validate_result = guard.validate(format_case.valid_object, SIMPLE_SCHEMA)
    repair_result = guard.repair(format_case.repairable_object)
    parsed = guard.parse(format_case.valid_object, SIMPLE_SCHEMA)

    assert validate_result.valid is True
    assert repair_result.repaired is True
    assert parsed == {"name": "Alice", "age": 30}


def test_output_guard_method_format_override(format_case: FormatCase) -> None:
    guard = OutputGuard(format="json")

    result = guard.validate(format_case.valid_object, SIMPLE_SCHEMA, format=format_case.name)

    assert result.valid is True
    assert result.format == format_case.name


@pytest.mark.parametrize(("fmt", "text"), AUTO_CASES)
def test_auto_and_forced_json_off_parse_multiple_formats(fmt: str, text: str) -> None:
    result = outputguard.validate(text, SIMPLE_SCHEMA, format=fmt)

    assert result.valid is True
    assert result.data == {"name": "Alice", "age": 30}
    assert result.format == fmt


@pytest.mark.parametrize(("fmt", "text"), AUTO_CASES)
def test_auto_and_forced_json_off_parse_convenience(fmt: str, text: str) -> None:
    assert outputguard.parse(text, SIMPLE_SCHEMA, format=fmt) == {"name": "Alice", "age": 30}


@pytest.mark.parametrize(("fmt", "text"), ALIAS_CASES)
def test_documented_format_aliases_parse(fmt: str, text: str) -> None:
    result = outputguard.validate(text, SIMPLE_SCHEMA, format=fmt)

    assert result.valid is True
    assert result.data == {"name": "Alice", "age": 30}
    assert result.format == fmt


def test_supported_formats_are_exported() -> None:
    assert set(outputguard.SUPPORTED_FORMATS) == {
        "json",
        "yaml",
        "toml",
        "python",
        "auto",
        "forced-json-off",
    }


def test_unsupported_format_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        outputguard.validate("{}", SIMPLE_SCHEMA, format="xml")


def test_retry_prompt_names_target_format() -> None:
    result = outputguard.validate("name: Alice\n", SIMPLE_SCHEMA, format="yaml")
    prompt = outputguard.retry_prompt("name: Alice\n", SIMPLE_SCHEMA, result.errors, format="yaml")

    assert "YAML" in prompt
    assert "age" in prompt


def _write_schema(tmp_path: Path) -> str:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(SIMPLE_SCHEMA))
    return str(schema_path)


@pytest.mark.parametrize("format_case", FORMAT_CASES, ids=lambda case: case.name)
def test_cli_validate_supported_format(tmp_path: Path, format_case: FormatCase) -> None:
    runner = CliRunner()
    input_path = tmp_path / f"valid.{format_case.name}"
    input_path.write_text(format_case.valid_object)

    result = runner.invoke(
        cli,
        [
            "validate",
            str(input_path),
            "-s",
            _write_schema(tmp_path),
            "--input-format",
            format_case.name,
        ],
    )

    assert result.exit_code == 0


@pytest.mark.parametrize("format_case", FORMAT_CASES, ids=lambda case: case.name)
def test_cli_validate_repairs_supported_format(tmp_path: Path, format_case: FormatCase) -> None:
    runner = CliRunner()
    input_path = tmp_path / f"repairable.{format_case.name}"
    input_path.write_text(format_case.repairable_object)

    result = runner.invoke(
        cli,
        [
            "validate",
            str(input_path),
            "-s",
            _write_schema(tmp_path),
            "--repair",
            "--input-format",
            format_case.name,
        ],
    )

    assert result.exit_code == 0


@pytest.mark.parametrize("format_case", FORMAT_CASES, ids=lambda case: case.name)
def test_cli_repair_supported_format(tmp_path: Path, format_case: FormatCase) -> None:
    runner = CliRunner()
    input_path = tmp_path / f"repairable.{format_case.name}"
    input_path.write_text(format_case.repairable_object)

    result = runner.invoke(
        cli, ["repair", str(input_path), "--input-format", format_case.name, "-f", "json"]
    )

    assert result.exit_code == 0
    payload: dict[str, Any] = json.loads(result.output)
    assert payload["repaired"] is True
    assert payload["format"] == format_case.name
