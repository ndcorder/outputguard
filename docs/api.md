# API Guide

This guide lists the public functions most users need. Import from
`outputguard` unless you are working inside the package.

```python
from outputguard import (
    validate,
    repair,
    validate_and_repair,
    parse,
    retry_prompt,
    guarded_generate,
    guarded_generate_async,
    validate_batch,
    repair_batch,
)
```

## Choosing an API

| Use case | Function |
| --- | --- |
| Validate one output against a JSON Schema | `validate()` |
| Validate, repair if needed, then validate again | `validate_and_repair()` |
| Repair syntax without a schema | `repair()` |
| Parse valid schema-matching data or raise | `parse()` |
| Build a retry prompt from validation errors | `retry_prompt()` |
| Wrap a sync LLM generation callable | `guarded_generate()` |
| Wrap an async LLM generation callable | `guarded_generate_async()` |
| Validate many outputs against one schema | `validate_batch()` |
| Repair many outputs without a schema | `repair_batch()` |

## Minimal Schema Example

Validation APIs require a JSON Schema dictionary.

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["name", "score"],
}
```

## Formats

Most APIs accept a `format` argument. The default is `"json"`.

Supported values:

- `"json"`
- `"yaml"` or `"yml"`
- `"toml"`
- `"python-literal"`, `"python"`, `"py"`, or `"literal"`
- `"auto"`
- `"forced-json-off"` or `"forced_json_off"`

See [formats.md](formats.md) for detailed behavior.

## `validate()`

Use this when you only need a validity check.

```python
from outputguard import validate

result = validate('{"name": "Ada", "score": 1}', schema)

if result.valid:
    print(result.data)
else:
    for error in result.errors:
        print(error.path, error.message)
```

`validate()` returns a `ValidationResult` with:

- `valid`: whether the parsed data matches the schema.
- `data`: parsed Python data when parsing succeeds.
- `errors`: validation or parse errors.
- `repaired`: always `False` for validate-only calls.
- `strategies_applied`: repair strategies used, if any.
- `original_text`: input text.
- `repaired_text`: repaired text, if any.
- `format`: resolved input format.

## `validate_and_repair()`

Use this for the common path: validate one model output, repair it when needed,
and validate the repaired output against the same schema.

```python
from outputguard import validate_and_repair

result = validate_and_repair("{name: 'Ada', score: 1,}", schema, format="json")

print(result.valid)
print(result.data)
print(result.repaired)
print(result.strategies_applied)
```

If the original text is already valid, no repair is applied. If repair succeeds,
`repaired=True` and `repaired_text` contains the repaired payload.

## `repair()`

Use this when you want schema-free syntax repair.

```python
from outputguard import repair

result = repair("{'name': 'Ada', 'active': True}", format="python-literal")

print(result.repaired)
print(result.text)
print(result.parse_error)
```

`repair()` returns a `RepairResult` with:

- `repaired`: whether the text changed.
- `text`: repaired or original text.
- `strategies_applied`: strategy names that changed the text.
- `parse_error`: parser error when repair cannot produce parseable data.
- `format`: resolved input format.

If you need a detailed repair report, use an `OutputGuard` instance:

```python
from outputguard import OutputGuard

guard = OutputGuard(format="json")
result, report = guard.repair("{name: 'Ada'}", report=True)
```

## `parse()`

Use this when invalid output should fail immediately.

```python
from outputguard import parse

payload = parse('{"name": "Ada", "score": 1}', schema)
```

`parse()` validates, attempts repair if needed, returns parsed Python data, or
raises `ParseError` / `SchemaValidationError`.

## `retry_prompt()`

Use this after a validation failure when you own the retry loop.

```python
from outputguard import retry_prompt, validate

result = validate(raw_text, schema)
if not result.valid:
    prompt = retry_prompt(raw_text, schema, result.errors)
```

The returned string explains what failed and asks the model to try again with
schema-compatible structured output.

By default, the retry prompt includes the previous model output in an
`Original output:` section. Turn that off when the prior output is too large or
should not be sent back to the model:

```python
prompt = retry_prompt(
    raw_text,
    schema,
    result.errors,
    include_message_history=False,
)
```

## `guarded_generate()`

Use this when you want OutputGuard to coordinate generation, validation, repair,
and retry in one call.

```python
from outputguard import guarded_generate

def generate(prompt: str, context) -> str:
    return call_model(prompt)

result = guarded_generate(
    prompt="Return a YAML object with name and score.",
    schema=schema,
    generate=generate,
    format="yaml",
    max_retries=2,
    include_message_history=False,
)

print(result.valid)
print(result.data)
print(result.attempts)
```

See [guarded-generation.md](guarded-generation.md) for result fields and retry
behavior.

## `guarded_generate_async()`

Use this with async model clients.

```python
from outputguard import guarded_generate_async

async def generate(prompt: str, context) -> str:
    return await call_model_async(prompt)

result = await guarded_generate_async(
    prompt="Return a JSON object with id and status.",
    schema=schema,
    generate=generate,
)
```

## Batch APIs

Use `validate_batch()` when you need validity and parsed data for many outputs.
Use `repair_batch()` when you need repaired text for many outputs without schema
validation.

```python
from outputguard import validate_batch, repair_batch

validation = validate_batch(["{'name': 'Ada', 'score': 1}"], schema, format="python-literal")
repairs = repair_batch(['{"name": "Ada",}'])
```

See [batch-processing.md](batch-processing.md) for result objects and CLI usage.

## Error Handling

OutputGuard raises package-specific exceptions for strict parse paths. The most
common 2.0 guarded-generation error is `GuardedGenerationError`, raised when
guarded generation cannot produce valid output within the retry budget and
`throw_on_failure=True`.

Use non-throwing result objects when you need to record failed attempts instead
of interrupting a pipeline.
