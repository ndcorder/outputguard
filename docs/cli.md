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

## Repair

Repair one output without schema validation:

```bash
outputguard repair response.txt
```

Write repaired text to a file:

```bash
outputguard repair response.txt --output repaired.json
```

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
| `--quiet`, `-q` | Suppress non-essential validation output |
| `--output`, `-o` | Write repaired or JSON output to a file |
| `--diff`, `-d` | Show a repair diff |
| `--verbose`, `-v` | Show per-strategy repair details |
| `--strategies` | Comma-separated repair strategy names for `repair` |
| `--no-message-history` | Omit the original output from `retry-prompt` output |

Run `outputguard --help` for the exact options supported by the installed
version.

## Exit Codes

The CLI uses conventional exit codes:

- `0`: command completed successfully and validation passed when applicable.
- `1`: validation or repair failed.
- `2`: command usage or input shape was invalid.

For automation, inspect both the exit code and `--format json` output when using
validation or batch commands.

## Format Notes

JSON is the default. Pass `--input-format` whenever the prompt expected another
format. Use `auto` for mixed historical output and `forced-json-off` when the
prompt explicitly told the model not to return JSON.
