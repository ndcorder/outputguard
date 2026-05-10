# Recipes

These recipes are small patterns you can paste into an application and adapt.

## Validate and Repair One Response

```python
result = outputguard.validate_and_repair(raw_output, schema)

if result.valid:
    return result.data

raise ValueError(result.errors)
```

Use this when you want one best effort repair before failing.

## Repair Without a Schema

```python
result = outputguard.repair(raw_output)

if result.parse_error:
    log_parse_failure(result.parse_error)
else:
    save_text(result.text)
```

Use this for cleanup jobs where you do not have a JSON Schema yet.

## Retry Without Repeating the Original Output

```python
result = outputguard.validate_and_repair(raw_output, schema)

if not result.valid:
    prompt = outputguard.retry_prompt(
        raw_output,
        schema,
        result.errors,
        include_message_history=False,
    )
```

Use this when the previous output is too large or should not be sent back to the
model.

## Custom Retry Loop

```python
prompt = "Return a JSON object with name and age."

for _ in range(3):
    raw = llm.generate(prompt)
    result = outputguard.validate_and_repair(raw, schema)
    if result.valid:
        return result.data
    prompt = outputguard.retry_prompt(raw, schema, result.errors)

raise RuntimeError("Model did not return valid structured output")
```

Use this when you need full control over model calls, tracing, or backoff.

## Guarded Generation Loop

```python
result = outputguard.guarded_generate(
    prompt="Return a JSON object with name and age.",
    schema=schema,
    generate=lambda prompt, context: llm.generate(prompt),
    max_retries=2,
    include_message_history=False,
)
```

Use this when you want OutputGuard to manage retry prompts and attempt history.

## YAML Output

```python
result = outputguard.validate_and_repair(
    raw_yaml,
    schema,
    format="yaml",
)
```

Use this when the model prompt asks for YAML. Do not rely on `auto` if your
prompt contract is known.

## Forced JSON Off

```python
result = outputguard.validate_and_repair(
    raw_output,
    schema,
    format="forced-json-off",
)
```

Use this when the model or provider setting explicitly disallows JSON mode.

## Validate an Eval Fixture

```python
outputs = load_outputs_from_fixture()
batch = outputguard.validate_batch(outputs, schema, repair=True)

assert batch.summary.invalid == 0
```

Use this in tests to prevent prompt changes from breaking structured output.

## CLI in CI

```bash
outputguard batch outputs.json --schema schema.json --repair --format json
```

The command exits non-zero when any item is invalid after repair.

## Log Failed Attempts

```python
result = outputguard.guarded_generate(
    prompt=prompt,
    schema=schema,
    generate=generate,
    max_retries=2,
)

for attempt in result.attempts:
    logger.info(
        "structured_output_attempt",
        extra={
            "attempt": attempt.attempt,
            "valid": attempt.result.valid,
            "errors": [error.message for error in attempt.result.errors],
        },
    )
```

Use attempt logs to improve prompts and compare model behavior.

