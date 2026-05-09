"""OutputGuard CLI — validate, repair, and inspect LLM JSON output."""

import dataclasses
import json
import sys

import click
from rich.console import Console
from rich.table import Table

import outputguard
from outputguard.models import ValidationResult, RepairResult
from outputguard.strategies import ALL_STRATEGIES

console = Console(stderr=True)


def _read_input(input_path: str) -> str:
    with click.open_file(input_path, "r") as f:
        return f.read()


def _load_schema(schema_path: str) -> dict:
    with open(schema_path, "r") as f:
        return json.load(f)


def _print_validation_text(result: ValidationResult) -> None:
    if result.valid:
        if result.repaired:
            console.print(
                "[yellow]⚠ Repaired and valid[/yellow]  "
                f"strategies: {', '.join(result.strategies_applied)}"
            )
        else:
            console.print("[green]✓ Valid[/green]")
    else:
        console.print("[red]✗ Invalid[/red]")
        for err in result.errors:
            console.print(f"  [red]{err.path}[/red]: {err.message}")


def _result_to_dict(obj: ValidationResult | RepairResult) -> dict:
    return dataclasses.asdict(obj)


def _write_output(text: str, output_path: str | None) -> None:
    if output_path:
        with open(output_path, "w") as f:
            f.write(text)
    else:
        click.echo(text)


@click.group()
def cli() -> None:
    """OutputGuard — validate and repair LLM JSON output."""


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option("-r", "--repair", "do_repair", is_flag=True, help="Attempt repair if validation fails.")
@click.option("-f", "--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.option("-q", "--quiet", is_flag=True, help="Exit code only, no output.")
@click.option("-o", "--output", "output_path", default=None, help="Write result to file.")
def validate(
    input_path: str,
    schema_path: str,
    do_repair: bool,
    fmt: str,
    quiet: bool,
    output_path: str | None,
) -> None:
    """Validate INPUT (file or - for stdin) against a JSON schema."""
    text = _read_input(input_path)
    schema = _load_schema(schema_path)

    if do_repair:
        result = outputguard.validate_and_repair(text, schema)
    else:
        result = outputguard.validate(text, schema)

    if not quiet:
        if fmt == "json":
            _write_output(json.dumps(_result_to_dict(result), indent=2), output_path)
        else:
            _print_validation_text(result)
            if result.valid and result.repaired and result.repaired_text:
                _write_output(result.repaired_text, output_path)

    sys.exit(0 if result.valid else 1)


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option("-f", "--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format.")
@click.option("-o", "--output", "output_path", default=None, help="Write result to file.")
@click.option("--strategies", default=None, help="Comma-separated strategy names.")
def repair(
    input_path: str,
    fmt: str,
    output_path: str | None,
    strategies: str | None,
) -> None:
    """Repair malformed JSON from INPUT (file or - for stdin)."""
    text = _read_input(input_path)
    strategy_list = [s.strip() for s in strategies.split(",")] if strategies else None

    guard = outputguard.OutputGuard(strategies=strategy_list)
    result = guard.repair(text)

    if fmt == "json":
        _write_output(json.dumps(_result_to_dict(result), indent=2), output_path)
    else:
        if result.repaired:
            console.print(
                "[yellow]⚠ Repaired[/yellow]  "
                f"strategies: {', '.join(result.strategies_applied)}"
            )
            _write_output(result.text, output_path)
        elif result.parse_error:
            console.print(f"[red]✗ Could not repair[/red]: {result.parse_error}")
        else:
            console.print("[green]✓ Already valid JSON[/green]")
            _write_output(result.text, output_path)

    sys.exit(0 if result.repaired or result.parse_error is None else 1)


@cli.command("retry-prompt")
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
def retry_prompt(input_path: str, schema_path: str) -> None:
    """Generate a retry prompt for invalid JSON from INPUT."""
    text = _read_input(input_path)
    schema = _load_schema(schema_path)

    result = outputguard.validate(text, schema)
    prompt = outputguard.retry_prompt(text, schema, result.errors)
    click.echo(prompt)
    sys.exit(0)


@cli.command()
def strategies() -> None:
    """List all available repair strategies."""
    table = Table(title="Repair Strategies")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")

    for i, (name, _fn) in enumerate(ALL_STRATEGIES, 1):
        table.add_row(str(i), name)

    console.print(table)
    sys.exit(0)
