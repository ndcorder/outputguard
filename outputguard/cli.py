"""OutputGuard CLI — validate, repair, and inspect LLM structured output."""

import dataclasses
import json
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

import outputguard
from outputguard.formats import CLI_FORMAT_CHOICES, format_label
from outputguard.guard import OutputGuard
from outputguard.models import RepairResult, ValidationResult
from outputguard.repairer import repair as _repair
from outputguard.strategies import ALL_STRATEGIES, STRATEGY_DESCRIPTIONS

console = Console(stderr=True)


def _read_input(input_path: str) -> str:
    with click.open_file(input_path, "r") as f:
        return f.read()


def _load_schema(schema_path: str) -> dict:
    with open(schema_path) as f:
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


def _dataclass_to_dict(obj: Any) -> dict:
    return dataclasses.asdict(obj)


def _write_output(text: str, output_path: str | None) -> None:
    if output_path:
        with open(output_path, "w") as f:
            f.write(text)
    else:
        click.echo(text)


@click.group()
def cli() -> None:
    """OutputGuard — validate and repair LLM structured output."""


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "-r", "--repair", "do_repair", is_flag=True, help="Attempt repair if validation fails."
)
@click.option(
    "--input-format",
    "input_format",
    type=click.Choice(CLI_FORMAT_CHOICES),
    default="json",
    show_default=True,
    help="Structured data format to parse.",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option("-q", "--quiet", is_flag=True, help="Exit code only, no output.")
@click.option("-o", "--output", "output_path", default=None, help="Write result to file.")
@click.option("-d", "--diff", "show_diff", is_flag=True, help="Show diff of repairs.")
@click.option("-v", "--verbose", is_flag=True, help="Show each strategy's effect.")
def validate(
    input_path: str,
    schema_path: str,
    do_repair: bool,
    input_format: str,
    fmt: str,
    quiet: bool,
    output_path: str | None,
    show_diff: bool,
    verbose: bool,
) -> None:
    """Validate INPUT (file or - for stdin) against a JSON schema."""
    text = _read_input(input_path)
    schema = _load_schema(schema_path)

    if do_repair:
        result = outputguard.validate_and_repair(text, schema, format=input_format)
    else:
        result = outputguard.validate(text, schema, format=input_format)

    if not quiet:
        if fmt == "json":
            _write_output(json.dumps(_result_to_dict(result), indent=2), output_path)
        else:
            _print_validation_text(result)
            if result.valid and result.repaired:
                if show_diff or verbose:
                    _show_repair_details(text, result, verbose, input_format)
                if result.repaired_text:
                    _write_output(result.repaired_text, output_path)

    sys.exit(0 if result.valid else 1)


def _show_repair_details(
    original: str, result: ValidationResult, verbose: bool, input_format: str
) -> None:
    """Show diff/verbose output for a repair."""
    if not result.repaired:
        return
    _result, report = _repair(original, report=True, format=input_format)
    if verbose:
        step_diffs = report.step_diffs()
        if step_diffs:
            console.print("\n[bold]Strategy details:[/bold]")
            console.print(step_diffs)
        console.print(f"[dim]Confidence: {report.confidence:.0%}[/dim]")
    else:
        diff = report.diff
        if diff:
            console.print("\n[bold]Diff:[/bold]")
            console.print(diff)


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.option("-o", "--output", "output_path", default=None, help="Write result to file.")
@click.option(
    "--input-format",
    "input_format",
    type=click.Choice(CLI_FORMAT_CHOICES),
    default="json",
    show_default=True,
    help="Structured data format to parse.",
)
@click.option("--strategies", default=None, help="Comma-separated strategy names.")
@click.option("-d", "--diff", "show_diff", is_flag=True, help="Show diff of repairs.")
@click.option("-v", "--verbose", is_flag=True, help="Show each strategy's effect.")
def repair(
    input_path: str,
    fmt: str,
    output_path: str | None,
    input_format: str,
    strategies: str | None,
    show_diff: bool,
    verbose: bool,
) -> None:
    """Repair malformed structured data from INPUT (file or - for stdin)."""
    text = _read_input(input_path)
    strategy_list = [s.strip() for s in strategies.split(",")] if strategies else None

    guard = OutputGuard(strategies=strategy_list, format=input_format)
    need_report = show_diff or verbose
    if need_report:
        result, report = guard.repair(text, report=True)
    else:
        result = guard.repair(text)
        report = None

    if fmt == "json":
        _write_output(json.dumps(_result_to_dict(result), indent=2), output_path)
    else:
        if result.repaired:
            console.print(
                f"[yellow]⚠ Repaired[/yellow]  strategies: {', '.join(result.strategies_applied)}"
            )
            if report and verbose:
                step_diffs = report.step_diffs()
                if step_diffs:
                    console.print("\n[bold]Strategy details:[/bold]")
                    console.print(step_diffs)
                console.print(f"[dim]Confidence: {report.confidence:.0%}[/dim]")
            elif report and show_diff:
                diff = report.diff
                if diff:
                    console.print("\n[bold]Diff:[/bold]")
                    console.print(diff)
            _write_output(result.text, output_path)
        elif result.parse_error:
            console.print(f"[red]✗ Could not repair[/red]: {result.parse_error}")
        else:
            console.print(f"[green]✓ Already valid {format_label(input_format)}[/green]")
            _write_output(result.text, output_path)

    sys.exit(0 if result.repaired or result.parse_error is None else 1)


@cli.command()
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "-r", "--repair", "do_repair", is_flag=True, help="Attempt repair if validation fails."
)
@click.option(
    "--input-format",
    "input_format",
    type=click.Choice(CLI_FORMAT_CHOICES),
    default="json",
    show_default=True,
    help="Structured data format to parse.",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
def batch(input_path: str, schema_path: str, do_repair: bool, input_format: str, fmt: str) -> None:
    """Validate a JSON array of structured-output strings."""
    payload = json.loads(_read_input(input_path))
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise click.ClickException("Batch input must be a JSON array of strings.")

    result = outputguard.validate_batch(
        payload, _load_schema(schema_path), repair=do_repair, format=input_format
    )

    if fmt == "json":
        click.echo(json.dumps(_dataclass_to_dict(result), indent=2))
    else:
        summary = result.summary
        if summary.invalid == 0:
            console.print(f"[green]✓ {summary.valid}/{summary.total} valid[/green]")
        else:
            console.print(
                f"[yellow]⚠ {summary.valid}/{summary.total} valid, "
                f"{summary.invalid} invalid[/yellow]"
            )
        if summary.repaired:
            console.print(f"[dim]Repaired: {summary.repaired}[/dim]")
        if summary.strategy_counts:
            console.print(f"[dim]Strategies: {summary.strategy_counts}[/dim]")

    sys.exit(0 if result.summary.invalid == 0 else 1)


@cli.command("retry-prompt")
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "--input-format",
    "input_format",
    type=click.Choice(CLI_FORMAT_CHOICES),
    default="json",
    show_default=True,
    help="Structured data format to parse.",
)
@click.option(
    "--message-history/--no-message-history",
    default=True,
    show_default=True,
    help="Include the original output in the retry prompt.",
)
def retry_prompt(
    input_path: str,
    schema_path: str,
    input_format: str,
    message_history: bool,
) -> None:
    """Generate a retry prompt for invalid structured output from INPUT."""
    text = _read_input(input_path)
    schema = _load_schema(schema_path)

    result = outputguard.validate(text, schema, format=input_format)
    prompt = outputguard.retry_prompt(
        text,
        schema,
        result.errors,
        format=input_format,
        include_message_history=message_history,
    )
    click.echo(prompt)
    sys.exit(0)


@cli.command()
def strategies() -> None:
    """List all available repair strategies."""
    table = Table(title="Repair Strategies")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for i, (name, _fn) in enumerate(ALL_STRATEGIES, 1):
        table.add_row(str(i), name, STRATEGY_DESCRIPTIONS.get(name, ""))

    console.print(table)
    sys.exit(0)


@cli.command()
def version() -> None:
    """Show outputguard version."""
    from importlib.metadata import version as pkg_version

    click.echo(f"outputguard {pkg_version('outputguard')}")
