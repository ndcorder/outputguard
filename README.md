# outputguard

Validate, repair, and retry LLM structured outputs.

LLMs frequently produce malformed JSON — markdown fences, trailing commas, unquoted keys, commentary text, JavaScript literals, and more. **outputguard** catches these issues, repairs them automatically, and validates the result against your JSON Schema.

## Features

- **9 repair strategies** for common LLM JSON malformations
- **JSON Schema validation** with detailed error paths
- **Validate-and-repair pipeline** — fix and re-validate in one call
- **Retry prompt generation** — get a correction prompt to send back to the LLM
- **Library API and CLI** — use from Python code or the command line
- **Configurable pipeline** — enable/disable individual strategies

## Installation

```bash
pip install outputguard
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add outputguard
```

## Quick Start

### Python API

```python
import outputguard

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    },
    "required": ["name", "age"]
}

# LLM returned markdown-fenced JSON with trailing commas
llm_output = '''```json
{"name": "Alice", "age": 30,}
```'''

result = outputguard.validate_and_repair(llm_output, schema)
print(result.valid)              # True
print(result.repaired)           # True
print(result.data)               # {'name': 'Alice', 'age': 30}
print(result.strategies_applied) # ['strip_fences', 'fix_commas']
```

### Retry Workflow

When repair isn't enough, generate a correction prompt for the LLM:

```python
result = outputguard.validate(llm_output, schema)
if not result.valid:
    prompt = outputguard.retry_prompt(llm_output, schema, result.errors)
    # Send `prompt` back to the LLM as a follow-up message
```

### CLI

```bash
# Validate JSON against a schema
outputguard validate output.json -s schema.json

# Validate with auto-repair
outputguard validate output.json -s schema.json --repair

# Repair only (no schema validation)
outputguard repair output.json

# Generate a retry prompt
outputguard retry-prompt output.json -s schema.json

# List available repair strategies
outputguard strategies

# Read from stdin
echo '{name: "Alice", age: 30,}' | outputguard repair -
```

## Repair Strategies

| Strategy | Description |
|---|---|
| `strip_fences` | Remove markdown code fences (`` ```json ... ``` ``) |
| `extract_json` | Extract JSON from surrounding commentary text |
| `remove_comments` | Strip JS-style `//` and `/* */` comments |
| `fix_commas` | Remove trailing commas before `}` and `]` |
| `fix_quotes` | Replace single quotes with double quotes |
| `fix_keys` | Add double quotes to unquoted object keys |
| `fix_values` | Replace `NaN`, `Infinity`, `undefined` with `null` |
| `fix_booleans` | Replace Python `True`/`False`/`None` with `true`/`false`/`null` |
| `fix_closers` | Balance missing closing braces and brackets |
| `fix_newlines` | Escape unescaped newlines inside string values |

Strategies are applied in order. Use a subset:

```python
from outputguard import OutputGuard

guard = OutputGuard(strategies=["strip_fences", "fix_commas"])
result = guard.validate_and_repair(text, schema)
```

## API Reference

### Module-level functions

- `validate(text, schema)` → `ValidationResult`
- `repair(text)` → `RepairResult`
- `validate_and_repair(text, schema)` → `ValidationResult`
- `retry_prompt(text, schema, errors)` → `str`

### `OutputGuard` class

```python
guard = OutputGuard(
    strategies=["strip_fences", "fix_commas"],  # None = all
    max_repair_attempts=3,
)
```

Methods: `validate()`, `repair()`, `validate_and_repair()`, `retry_prompt()`

### Data classes

- **`ValidationResult`**: `valid`, `data`, `errors`, `repaired`, `strategies_applied`, `original_text`, `repaired_text`
- **`RepairResult`**: `repaired`, `text`, `strategies_applied`, `parse_error`
- **`ValidationError`**: `message`, `path`, `schema_path`, `value`

## License

MIT
