# CLI Guide

The `outputguard` command validates and repairs structured output from files or
stdin. The CLI is organized around subcommands.

## Install

```bash
pip install outputguard
```

## Validate

Validate one output against a JSON Schema file:

```bash
outputguard validate response.txt --schema schema.json
```

Validate and repair if needed:

```bash
outputguard validate response.txt --schema schema.json --repair
```

Use a non-JSON format:

```bash
outputguard validate response.yaml --schema schema.json --input-format yaml
```

Read from stdin:

```bash
cat response.txt | outputguard validate - --schema schema.json
```

Input and schema files use strict UTF-8. Input text preserves line endings and
an authored BOM; the selected parser decides whether a BOM is allowed. Large or
slow pipes are read through EOF, and JSON output is flushed before the process
exits.

Short options can be combined (`-rq`) and values can be attached (`-fjson`,
`-sschema.json`). Options can appear before or after INPUT. Use `--` before a
filename beginning with a dash:

```bash
outputguard validate -s schema.json -fjson -- --response.json
```

## Repair

Repair one output without schema validation:

```bash
outputguard repair response.txt
```

Write repaired text to a file:

```bash
outputguard repair response.txt --output repaired.json
```

`--output -` writes to stdout. Quiet validation suppresses the result, details,
and output-file writes, including when JSON output is requested. Repairing an
already-valid document exits successfully and returns the original text.

Inspect repairs:

```bash
outputguard repair response.txt --diff
outputguard repair response.txt --verbose
```

## Retry Prompt

Generate feedback for an invalid output:

```bash
outputguard retry-prompt response.txt --schema schema.json
```

Omit the original output from the generated retry prompt:

```bash
outputguard retry-prompt response.txt --schema schema.json --no-message-history
```

For an already-valid document, this command emits a status message on stderr
and no retry prompt. Repeated `--message-history` / `--no-message-history` flags
use the last setting.

## Batch

The batch command reads a JSON array of strings and validates each item against
one JSON Schema.

```bash
outputguard batch outputs.json --schema schema.json --input-format auto
outputguard batch outputs.json --schema schema.json --repair --input-format json
```

Emit machine-readable JSON:

```bash
outputguard batch outputs.json --schema schema.json --repair --format json
```

## Strategies and Version

```bash
outputguard strategies
outputguard version
```

## Common Flags

| Flag | Meaning |
| --- | --- |
| `--schema`, `-s` | JSON Schema file path for validation commands |
| `--repair`, `-r` | Attempt repair before final validation |
| `--input-format` | Input format: `json`, `yaml`, `toml`, `python`, `auto`, or `forced-json-off` |
| `--format`, `-f` | CLI output format: `text` or `json` |
| `--quiet`, `-q` | Exit code only; suppress result output and output-file writes |
| `--output`, `-o` | Write repaired or JSON output to a file |
| `--diff`, `-d` | Show a repair diff |
| `--verbose`, `-v` | Show per-strategy repair details |
| `--strategies` | Comma-separated repair strategy names for `repair` |
| `--no-message-history` | Omit the original output from `retry-prompt` output |
| `--message-history` | Include the original output (the default) |
| `--help`, `-h` | Show root or subcommand help |

Run `outputguard --help` for the exact options supported by the installed
version.

`--strategies` accepts exact, case-sensitive names, with surrounding whitespace
trimmed from each comma-separated name. Strategies run once in registry order.
Omit the option to use all strategies; `--strategies ''` (or whitespace only)
disables repair. Unknown names and empty elements inside a comma-separated list
are usage errors (exit 2), checked before reading input files or stdin.

## Exit Codes

The CLI uses conventional exit codes:

- `0`: command completed successfully and validation passed when applicable.
- `1`: validation, repair, file I/O, decoding, or schema processing failed.
- `2`: command usage, batch transport, or schema JSON/root shape was invalid.

For automation, inspect both the exit code and `--format json` output when using
validation or batch commands.

Human status, repair details, and errors go to stderr. JSON reports, repaired
text, retry prompts, help, and version output go to stdout unless an output file
is selected. Usage and I/O errors produce diagnostics rather than a partial JSON
report. `--quiet` applies to validation results, while usage and I/O errors are
still reported.

Failed repairs return the original text in JSON reports and do not write a
repaired-text file. `--verbose` in text mode shows changes from the final
attempt, including discarded edits, and any recorded strategy errors.
Diffs use unified hunks with three context lines and missing-final-newline
markers. Detail bodies preserve long lines, LF/CRLF, and literal markup without
terminal wrapping or Rich formatting.

JSON repair output always contains the repair result, including with `--diff`
or `--verbose`. Reports use each language API's field names (snake_case in
Python, camelCase in JavaScript). Non-finite numeric values become JSON `null`;
the source text remains available in validation reports. `NO_COLOR` disables
terminal styling.

## Format Notes

JSON is the default. Pass `--input-format` whenever the prompt expected another
format. Use `auto` for mixed historical output and `forced-json-off` when the
prompt explicitly told the model not to return JSON.

All API aliases are accepted, including `py`, `yml`, and `forced_json_off`.
Input format names use the API's case and whitespace rules, and report metadata
preserves the supplied spelling. Output `--format` accepts `text` or `json`.
