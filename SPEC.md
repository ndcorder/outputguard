# outputguard — LLM Structured Output Validator & Repairer

## Overview

outputguard validates, repairs, and retries LLM structured outputs. LLM JSON outputs fail at approximately 6% rate in production due to trailing commas, unquoted keys, markdown code fences, extra commentary, and other malformations. outputguard validates output against JSON Schema, auto-repairs common patterns, and supports retry-with-feedback workflows. Works as both a Python library and CLI.

## Problem

LLMs frequently produce malformed JSON:
- Wrapping JSON in markdown code fences (````json ... `````)
- Adding commentary before/after the JSON
- Trailing commas in arrays and objects
- Single quotes instead of double quotes
- Unquoted property keys
- Missing closing braces or brackets
- JavaScript-style comments (`//` and `/* */`)
- NaN, Infinity, undefined literals
- Truncated output (incomplete JSON)

These errors break downstream parsers and require manual intervention or brittle regex fixes.

## Architecture

```
Input String
     |
  Validate against JSON Schema
     |
  Pass? → Return validated result
     |
  Fail → Attempt repair pipeline
     |
  +---+---+---+---+---+---+
  |   |   |   |   |   |   |
Strip Extract Fix   Fix  Fix  Fix
fences JSON   commas quotes keys braces
  |   |   |   |   |   |   |
  +---+---+---+---+---+---+
     |
  Re-validate
     |
  Pass? → Return repaired result
     |
  Fail → Generate retry prompt with errors
```

## Repair Strategies

Each strategy is a function that takes a string and returns a string. They are applied in order:

| Order | Strategy | Description |
|-|-|-|
| 1 | `strip_markdown_fences` | Remove ````json`, ````, and language-tagged fences |
| 2 | `extract_json_from_text` | Find the first `{...}` or `[...]` block in surrounding text |
| 3 | `remove_comments` | Strip `//` and `/* */` comments |
| 4 | `fix_trailing_commas` | Remove commas before `}` or `]` |
| 5 | `fix_single_quotes` | Replace single-quoted strings with double-quoted |
| 6 | `fix_unquoted_keys` | Add quotes to unquoted object keys |
| 7 | `fix_special_values` | Replace `NaN`, `Infinity`, `undefined` with `null` |
| 8 | `fix_missing_closers` | Append missing `}` or `]` to balance brackets |
| 9 | `fix_newlines_in_strings` | Escape unescaped newlines inside string values |

Strategies can be individually enabled/disabled via configuration.

## Library API

```python
import outputguard

# Simple validation
result = outputguard.validate(text, schema)
# Returns: ValidationResult(valid=True/False, data=parsed_dict, errors=[...])

# Repair only (no schema)
result = outputguard.repair(text)
# Returns: RepairResult(repaired=True/False, text=cleaned_string, strategies_applied=[...])

# Validate, then repair if needed
result = outputguard.validate_and_repair(text, schema)
# Returns: ValidationResult with repaired=True if repair was needed

# Generate a retry prompt
prompt = outputguard.retry_prompt(text, schema, errors)
# Returns: str — a prompt asking the LLM to fix specific errors

# Configure strategies
guard = outputguard.OutputGuard(
    strategies=["strip_markdown_fences", "fix_trailing_commas", "extract_json_from_text"],
    max_repair_attempts=3,
)
result = guard.validate_and_repair(text, schema)
```

## Result Types

```python
@dataclass
class ValidationResult:
    valid: bool
    data: dict | list | None      # Parsed data if valid
    errors: list[ValidationError]  # JSON Schema validation errors
    repaired: bool = False         # True if repair was applied
    strategies_applied: list[str] = field(default_factory=list)
    original_text: str = ""
    repaired_text: str = ""

@dataclass
class ValidationError:
    message: str
    path: str          # JSON path to the error, e.g. "$.items[0].name"
    schema_path: str   # Path in schema that was violated
    value: Any = None  # The offending value

@dataclass
class RepairResult:
    repaired: bool
    text: str
    strategies_applied: list[str]
    parse_error: str | None = None  # If repair failed, the parse error
```

## CLI

### `outputguard validate <input> --schema <schema>`

Validate a file or stdin against a JSON Schema.

Flags:
- `--schema / -s` — path to JSON Schema file (required)
- `--repair / -r` — attempt repair if validation fails (default: off)
- `--format / -f` — output format: `text`, `json` (default: text)
- `--quiet / -q` — exit code only, no output
- `--output / -o` — write repaired output to file

Input can be a file path or `-` for stdin.

### `outputguard repair <input>`

Attempt to repair malformed JSON (no schema validation).

Flags:
- `--format / -f` — output format: `text`, `json`
- `--output / -o` — write repaired output to file
- `--strategies` — comma-separated list of strategies to apply

### `outputguard retry-prompt <input> --schema <schema>`

Generate a correction prompt for an LLM.

Flags:
- `--schema / -s` — path to JSON Schema file

### `outputguard strategies`

List all available repair strategies.

## Exit Codes

- `0` — valid (or successfully repaired with `--repair`)
- `1` — invalid and could not be repaired
- `2` — usage error

## Retry-with-Feedback Prompt

When validation fails even after repair, `outputguard.retry_prompt()` generates a prompt like:

```
The JSON output you provided does not match the required schema. Please fix the following errors and return ONLY valid JSON:

Errors:
1. $.items[0].price: expected number, got string
2. $.metadata: required property "timestamp" is missing

Expected schema:
{schema_summary}

Your previous output (first 500 chars):
{truncated_output}

Return ONLY the corrected JSON with no additional text.
```

## JSON Schema Support

outputguard uses `jsonschema` for validation. Supported JSON Schema features:
- type, properties, required, additionalProperties
- items (array validation)
- enum, const
- minimum, maximum, minLength, maxLength
- pattern (regex)
- oneOf, anyOf, allOf
- $ref (local references)
- format (date, email, uri, etc.)

## Package & Distribution

- Python 3.10+
- Published to PyPI as `outputguard`
- Entry point: `outputguard` CLI via Click
- Dependencies: Click, jsonschema, rich

## Testing

- Unit tests for each repair strategy with known malformed inputs
- Tests for validation against various schemas
- Tests for validate_and_repair pipeline
- Tests for retry prompt generation
- Tests for edge cases (empty input, binary data, huge input)
- CLI tests with Click's CliRunner
- Test with real-world LLM output samples (embedded as fixtures)
