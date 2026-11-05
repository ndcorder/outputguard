# Guarded Generation Guide

Guarded generation wraps your LLM call with OutputGuard. You provide the model
callable. OutputGuard validates the response against your schema, optionally
repairs it, and retries with structured feedback when the output is still
invalid.

The prompt must be a string. Its type is checked before the provider or observer
is called, including when repair is disabled. Provider results must be strings
(or supported async results resolving to strings).

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
def generate(prompt: str, context) -> str: ...
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

## Configuration and Retry Limits

`max_retries` counts retries after the first call: zero permits one generation
attempt, and two permits at most three. `max_repair_attempts` on `OutputGuard`
counts repair passes; zero disables them. Both limits must be nonnegative whole
numbers from 0 to 9007199254740991. Integral floats such as `3.0` mean three;
fractions, booleans, strings, negative values, and non-finite numbers are rejected.

The wrapper checks retry limits, selected format, schema-root type, and callback
callability before invoking the provider or observer. Invalid configuration
raises directly and does not produce an exhausted result or consume model calls.
An omitted format or `None` inherits the guard; an empty string is invalid.

Providers must return text. A non-string result raises `TypeError` after that
provider call, before validation or observer notification, and causes no retry.
Exceptions from providers and observers also propagate directly.

The async wrapper accepts synchronous or asynchronous providers and observers.
Use `guarded_generate_async()` for async callbacks. The synchronous wrapper
rejects declared async callbacks before invoking the provider; if a synchronous
callback returns an awaitable, it raises rather than silently discarding it.
Fresh, unstarted coroutines returned in that situation are closed.

## Message History in Retry Prompts

Retry prompts include the previous model output by default. That gives the model
more context for fixing its own response, but it can add tokens or repeat data
you do not want to send again. Pass `include_message_history=False` to omit the
`Original output:` section from generated retry prompts.

```python
result = guarded_generate(
    prompt="Return a JSON object with name and score.",
    schema=schema,
    generate=generate,
    include_message_history=False,
)
```

Schema evaluation failures raise `SchemaEvaluationError` with the parsed data,
schema, format, and underlying cause. They abort the wrapper before observer
notification or any retry, even when ordinary exhaustion is configured to return
a result. Update the schema or reduce the recursion before another call.

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

`GuardedGenerationError` derives from `OutputGuardError`, so a common library
error handler catches exhausted generation too. Its `result` contains the full
failed result, including every attempt, final errors, and repair metadata.

The failure flag controls exhausted validation attempts. Provider and observer
failures propagate unchanged and stop the loop immediately; they do not consume
additional retries. Cancellation also propagates without being converted to a
generation failure.

## Repair Behavior

`repair=True` is useful for normal LLM output, where small syntax mistakes are
common. `repair=False` is useful when you want failed attempts to produce direct
validation feedback instead of repaired output.

Guarded generation validates against your schema either way.

When syntax repair succeeds but schema validation fails, the next attempt
receives the repaired text and the remaining schema errors. Attempt history
retains both the raw output and the repaired validation result, and repair
statistics include repairs from invalid attempts.

Retry prompts include the previous output by default. The excerpt preserves
up to 500 Unicode code points; longer text keeps the first and last 250 points
with an ellipsis line between them. The full previous text stays in attempt
records and the next call's context. Disabling message history omits this
excerpt; validation messages can still include offending values.

Retry feedback includes applicable object and array details for nullable or
typeless containers. Schema summaries stop after two nested container levels
and leave referenced constraints to validation errors.

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
