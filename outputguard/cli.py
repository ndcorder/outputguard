"""OutputGuard CLI — validate, repair, and inspect LLM structured output."""

import dataclasses
import json
import math
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

import outputguard
from outputguard.formats import (
    _FORMAT_WHITESPACE,
    CLI_FORMAT_CHOICES,
    FormatParseError,
    format_label,
    normalize_format,
    parse_document,
)
from outputguard.guard import OutputGuard
from outputguard.models import Schema, ValidationResult
from outputguard.repairer import repair as _repair
from outputguard.strategies import ALL_STRATEGIES, STRATEGY_DESCRIPTIONS

console = Console(stderr=True)


def _write_details(text: str) -> None:
    # Patch bodies must retain literal markup, long lines, and CRLF bytes.
    click.echo(text.encode("utf-8"), err=True, nl=not text.endswith("\n"))


class _CLICommand(click.Command):
    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except click.ClickException:
            raise
        except BrokenPipeError:
            raise  # Click handles EPIPE and suppresses a second flush failure.
        except Exception as error:
            # Native validation and I/O failures are operational CLI errors.
            # Library APIs retain their original exceptions and tracebacks.
            raise click.ClickException(str(error) or type(error).__name__) from error


class _CLIGroup(click.Group):
    def parse_args(self, ctx, args):
        if not args and not ctx.resilient_parsing:
            click.echo(ctx.get_help(), err=True, color=ctx.color)
            ctx.exit(2)
        return super().parse_args(ctx, args)

    def resolve_command(self, ctx, args):
        name = args[0]
        command = self.get_command(ctx, name)
        if command is None and ctx.token_normalize_func is not None:
            name = ctx.token_normalize_func(name)
            command = self.get_command(ctx, name)
        if command is None and not ctx.resilient_parsing:
            # Older Click reparses an empty list and treats any punctuation as
            # an option prefix. Use the original arguments and the CLI prefix.
            if name.startswith("-"):
                self.parse_args(ctx, args)
            ctx.fail(f"No such command {args[0]!r}.")
        return name if command else None, command, args[1:]


class _InputFormat(click.ParamType):
    name = "input format"

    def convert(self, value, param, ctx):
        try:
            normalize_format(value)
        except (TypeError, ValueError) as error:
            self.fail(str(error), param, ctx)
        return value

    def get_metavar(self, param=None, ctx=None):
        return "[" + "|".join(CLI_FORMAT_CHOICES) + "]"


_INPUT_FORMAT = _InputFormat()


def _read_input(input_path: str) -> str:
    with click.open_file(input_path, "rb") as f:
        return f.read().decode("utf-8")


def _load_schema(schema_path: str) -> Schema:
    with open(schema_path, "rb") as f:
        text = f.read().decode("utf-8")
    try:
        schema = parse_document(text, "json")
    except FormatParseError as error:
        raise click.BadParameter(
            f"Invalid JSON schema file: {error}", param_hint="--schema"
        ) from error
    if not isinstance(schema, (dict, bool)):
        raise click.BadParameter("Schema must be a JSON object or boolean", param_hint="--schema")
    return schema


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


def _json_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {
            ("NaN" if math.isnan(key) else "-Infinity" if key < 0 else "Infinity")
            if isinstance(key, float) and not math.isfinite(key)
            else key: _json_value(item)
            for key, item in value.items()
        }
    return value


def _json_output(obj: Any) -> str:
    # Match JSON.stringify's null representation for non-finite values.
    return json.dumps(_json_value(dataclasses.asdict(obj)), indent=2, allow_nan=False)


def _write_output(text: str, output_path: str | None) -> None:
    if output_path and output_path != "-":
        with open(output_path, "wb") as f:
            f.write(text.encode("utf-8"))
    else:
        click.echo(text.encode("utf-8"), nl=not text.endswith("\n"))


@click.group(
    cls=_CLIGroup,
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
def cli() -> None:
    """OutputGuard — validate and repair LLM structured output."""


@cli.command(cls=_CLICommand)
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "-r", "--repair", "do_repair", is_flag=True, help="Attempt repair if validation fails."
)
@click.option(
    "--input-format",
    "input_format",
    type=_INPUT_FORMAT,
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
            _write_output(_json_output(result), output_path)
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
            _write_details(step_diffs)
        console.print(f"[dim]Confidence: {report.confidence:.0%}[/dim]")
    else:
        diff = report.diff
        if diff:
            console.print("\n[bold]Diff:[/bold]")
            _write_details(diff)


@cli.command(cls=_CLICommand)
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
    type=_INPUT_FORMAT,
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
    strategy_list = None
    if strategies is not None:
        strategy_list = (
            [s.strip(_FORMAT_WHITESPACE) for s in strategies.split(",")]
            if strategies.strip(_FORMAT_WHITESPACE)
            else []
        )
    try:
        guard = OutputGuard(strategies=strategy_list, format=input_format)
    except (TypeError, ValueError) as error:
        raise click.BadParameter(str(error), param_hint="--strategies") from error
    text = _read_input(input_path)
    need_report = show_diff or verbose
    if need_report:
        result, report = guard.repair(text, report=True)
    else:
        result = guard.repair(text)
        report = None

    if fmt == "json":
        _write_output(_json_output(result), output_path)
    else:
        if result.repaired:
            console.print(
                f"[yellow]⚠ Repaired[/yellow]  strategies: {', '.join(result.strategies_applied)}"
            )
        elif result.parse_error:
            console.print(f"[red]✗ Could not repair[/red]: {result.parse_error}")
        else:
            console.print(f"[green]✓ Already valid {format_label(input_format)}[/green]")
        if report and report.steps:
            if verbose:
                step_diffs = report.step_diffs()
                if step_diffs:
                    console.print("\n[bold]Strategy details:[/bold]")
                    _write_details(step_diffs)
                console.print(f"[dim]Confidence: {report.confidence:.0%}[/dim]")
            elif show_diff:
                diff = report.diff
                if diff:
                    console.print("\n[bold]Diff:[/bold]")
                    _write_details(diff)
        if result.parse_error is None:
            _write_output(result.text, output_path)

    sys.exit(0 if result.repaired or result.parse_error is None else 1)


@cli.command(cls=_CLICommand)
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "-r", "--repair", "do_repair", is_flag=True, help="Attempt repair if validation fails."
)
@click.option(
    "--input-format",
    "input_format",
    type=_INPUT_FORMAT,
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
    text = _read_input(input_path)
    try:
        payload = parse_document(text, "json")
    except FormatParseError as error:
        raise click.BadParameter(
            "Batch input must be a JSON array of strings", param_hint="INPUT"
        ) from error
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise click.BadParameter("Batch input must be a JSON array of strings", param_hint="INPUT")

    result = outputguard.validate_batch(
        payload, _load_schema(schema_path), repair=do_repair, format=input_format
    )

    if fmt == "json":
        _write_output(_json_output(result), None)
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


@cli.command("retry-prompt", cls=_CLICommand)
@click.argument("input_path", metavar="INPUT")
@click.option("-s", "--schema", "schema_path", required=True, help="Path to JSON Schema file.")
@click.option(
    "--input-format",
    "input_format",
    type=_INPUT_FORMAT,
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
    if result.valid:
        console.print("[green]✓ Already valid; no retry prompt needed[/green]")
        sys.exit(0)
    prompt = outputguard.retry_prompt(
        text,
        schema,
        result.errors,
        format=input_format,
        include_message_history=message_history,
    )
    _write_output(prompt, None)
    sys.exit(0)


@cli.command(cls=_CLICommand)
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


@cli.command(cls=_CLICommand)
def version() -> None:
    """Show outputguard version."""
    from importlib.metadata import version as pkg_version

    click.echo(f"outputguard {pkg_version('outputguard')}")
