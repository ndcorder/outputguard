# Migration to 2.0

OutputGuard 2.0 keeps the JSON-first API intact and adds new structured-output
workflows. Most 1.x code does not need to change.

## What Stayed the Same

These calls still default to JSON:

```python
outputguard.validate(text, schema)
outputguard.repair(text)
outputguard.validate_and_repair(text, schema)
outputguard.parse(text, schema)
outputguard.retry_prompt(text, schema, errors)
```

Existing JSON prompts and JSON Schema validation continue to work.

## What Changed

2.0 adds:

- `format=` for JSON, YAML, TOML, Python literals, `auto`, and
  `forced-json-off`.
- `guarded_generate()` and `guarded_generate_async()`.
- `validate_batch()` and `repair_batch()`.
- `outputguard batch`.
- `include_message_history=False` for retry prompts that should not repeat prior
  model output.

## Adopt Formats Gradually

Start by keeping existing JSON code unchanged. Add `format=` only where prompts
return another structured format.

```python
result = outputguard.validate_and_repair(raw_yaml, schema, format="yaml")
```

## Replace Custom Retry Loops When Useful

If your application has a hand-written retry loop, you can keep it. If it only
does validation, repair, and retry prompt generation, consider replacing it with
`guarded_generate()`.

```python
result = outputguard.guarded_generate(
    prompt=prompt,
    schema=schema,
    generate=generate,
    max_retries=2,
)
```

## Review Retry Prompt History

Before 2.0, retry prompts always included the previous output. That remains the
default. New code can opt out:

```python
prompt = outputguard.retry_prompt(
    raw,
    schema,
    errors,
    include_message_history=False,
)
```

Use the opt-out for large outputs, sensitive outputs, or chat systems that
already include prior messages separately.

## Use Batch APIs for Fixtures and Logs

If you have scripts that loop over saved outputs, move them to batch APIs:

```python
batch = outputguard.validate_batch(outputs, schema, repair=True)
```

The summary gives counts for valid, invalid, repaired, parse failures, schema
failures, strategy usage, and formats.

## CLI Changes

Validation and repair commands accept `--input-format`. Batch validation is now
available:

```bash
outputguard batch outputs.json --schema schema.json --repair
```

Retry prompts can omit prior output:

```bash
outputguard retry-prompt response.txt --schema schema.json --no-message-history
```

## Migration Checklist

- Keep existing JSON calls unchanged.
- Add explicit `format=` for non-JSON prompt contracts.
- Decide whether retry prompts should include previous output.
- Move eval fixtures or saved logs to `validate_batch()` or `outputguard batch`.
- Add tests around the exact formats your prompts request.

