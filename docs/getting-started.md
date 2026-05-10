# Getting Started

This guide takes you from installation to a production-shaped retry loop. It
uses JSON because JSON is the default, then shows where to add formats, CLI
usage, and guarded generation.

## 1. Install

```bash
pip install outputguard
```

With uv:

```bash
uv add outputguard
```

## 2. Start With a Schema

Validation APIs use JSON Schema. The schema describes the parsed data you want,
not the exact text the model should return.

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}
```

## 3. Validate Good Output

```python
import outputguard

result = outputguard.validate('{"name": "Ada", "age": 30}', schema)

assert result.valid is True
assert result.data == {"name": "Ada", "age": 30}
```

`validate()` parses the text, validates the parsed data against the schema, and
returns a `ValidationResult`. It does not repair anything.

## 4. Repair Common Model Mistakes

Models often return almost-valid structured output:

```python
raw = """```json
{name: 'Ada', age: 30,}
```"""

result = outputguard.validate_and_repair(raw, schema)

if result.valid:
    print(result.data)
    print(result.strategies_applied)
```

`validate_and_repair()` first validates the raw text. If it fails, OutputGuard
applies repair strategies and validates the repaired text.

## 5. Decide How Strict You Want to Be

Use the result object when failures are expected and should be logged:

```python
result = outputguard.validate_and_repair(raw, schema)
if not result.valid:
    log_errors(result.errors)
```

Use `parse()` when invalid output should raise:

```python
data = outputguard.parse(raw, schema)
```

`parse()` is useful at boundaries where the application cannot continue without
schema-compatible data.

## 6. Generate a Retry Prompt

When repair is not enough, send the model a targeted correction prompt:

```python
result = outputguard.validate_and_repair(raw, schema)

if not result.valid:
    prompt = outputguard.retry_prompt(raw, schema, result.errors)
```

By default the retry prompt includes the previous model output. Omit it when the
output is too large or should not be sent back:

```python
prompt = outputguard.retry_prompt(
    raw,
    schema,
    result.errors,
    include_message_history=False,
)
```

## 7. Wrap the Whole Generation Loop

`guarded_generate()` calls your model function, validates the result, optionally
repairs it, and retries with validation feedback.

```python
def generate(prompt: str, context) -> str:
    return llm.generate(prompt)

result = outputguard.guarded_generate(
    prompt="Return a JSON object with name and age.",
    schema=schema,
    generate=generate,
    max_retries=2,
)

if result.valid:
    use_user(result.data)
else:
    log_failed_attempts(result.attempts)
```

Async model clients use `guarded_generate_async()` with the same options.

## 8. Use Non-JSON Formats Explicitly

JSON remains the default. Pass `format=` when the prompt asks for YAML, TOML, or
Python literal output.

```python
result = outputguard.validate_and_repair(
    "name: Ada\nage: 30\n",
    schema,
    format="yaml",
)
```

Use `format="auto"` for mixed historical data. Prefer explicit formats for new
prompts because failures are easier to understand.

## 9. Try the CLI

Create `schema.json` and `response.txt`, then run:

```bash
outputguard validate response.txt --schema schema.json --repair
```

Generate a retry prompt:

```bash
outputguard retry-prompt response.txt --schema schema.json
```

Omit the original output from that retry prompt:

```bash
outputguard retry-prompt response.txt --schema schema.json --no-message-history
```

## 10. Where to Go Next

- Use [API guide](api.md) for exact function signatures and result fields.
- Use [Formats guide](formats.md) when prompts return YAML, TOML, or Python
  literals.
- Use [Guarded generation guide](guarded-generation.md) for production retry
  loops.
- Use [Recipes](recipes.md) for copy-paste patterns.
- Use [Troubleshooting](troubleshooting.md) when a model output still fails.

