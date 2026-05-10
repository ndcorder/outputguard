# Guarded Generation Guide

Guarded generation wraps your LLM call with OutputGuard. You provide the model
callable. OutputGuard validates the response against your schema, optionally
repairs it, and retries with structured feedback when the output is still
invalid.

## When to Use It

Use guarded generation when:

- A downstream system expects schema-compatible structured data.
- You want retry attempts to include validation feedback.
- You need a record of each generation attempt.
- You want one reusable wrapper around different model providers.

Use lower-level APIs such as `validate_and_repair()` when you already have the
model output and do not need OutputGuard to call the model.

## Generator Signature

Your sync generator receives the current prompt and a context object.

```python
def generate(prompt: str, context) -> str:
    ...
```

The context contains:

- `attempt`: zero-based attempt number.
- `prompt`: the prompt for this attempt.
- `previous_text`: previous raw or repaired text, if any.
- `previous_result`: previous validation result, if any.

## Sync Example

```python
from outputguard import guarded_generate

schema = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "score": {"type": "number"}},
    "required": ["name", "score"],
}

def generate(prompt: str, context) -> str:
    return client.responses.create(
        model="example-model",
        input=prompt,
    ).output_text

result = guarded_generate(
    prompt="Return a JSON object with name and score.",
    schema=schema,
    generate=generate,
    format="json",
    max_retries=2,
)

print(result.valid)
print(result.data)
```

## Async Example

```python
from outputguard import guarded_generate_async

async def generate(prompt: str, context) -> str:
    response = await client.responses.create(
        model="example-model",
        input=prompt,
    )
    return response.output_text

result = await guarded_generate_async(
    prompt="Return a YAML object with name and score.",
    schema=schema,
    generate=generate,
    format="yaml",
)
```

## What OutputGuard Does Per Attempt

For each attempt, OutputGuard:

1. Calls your `generate` function with the prompt and context.
2. Validates the model output using the selected format and schema.
3. Repairs the output when `repair=True`.
4. Parses the repaired output into Python data.
5. Stops on success or prepares feedback for the next attempt.

The original prompt remains yours. OutputGuard only builds retry feedback when
an attempt fails validation or repair.

## Result Fields

Guarded generation returns `GuardedGenerateResult`.

Common fields:

- `valid`: whether valid parsed data was produced.
- `data`: parsed Python data when generation succeeds.
- `text`: final raw or repaired text.
- `attempts`: per-attempt records.
- `errors`: final validation errors when generation fails.
- `repaired`: whether any attempt required repair.
- `strategies_applied`: unique repair strategies used across attempts.
- `exhausted`: whether all retries were used.
- `format`: requested or resolved format.

Attempt records include the attempt number, prompt, raw model text, and
`ValidationResult`.

## Failure Behavior

If generation fails after all attempts, you have two choices:

- Set `throw_on_failure=True` to raise `GuardedGenerationError`.
- Set `throw_on_failure=False` to receive a failed result object with attempt
  history.

Use throwing behavior for request/response paths where invalid data cannot
continue. Use non-throwing behavior for batch jobs, evals, and logging.

## Repair Behavior

`repair=True` is useful for normal LLM output, where small syntax mistakes are
common. `repair=False` is useful when you want failed attempts to produce direct
validation feedback instead of repaired output.

Guarded generation validates against your schema either way.

## Observing Attempts

Use `on_attempt` to log each attempt.

```python
def observe(attempt) -> None:
    print(attempt.attempt, attempt.result.valid)

result = guarded_generate(
    prompt="Return a JSON object with name and score.",
    schema=schema,
    generate=generate,
    on_attempt=observe,
)
```

