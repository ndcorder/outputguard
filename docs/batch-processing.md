# Batch Processing Guide

Batch processing is for validating or repairing many model outputs at once. It
is useful for evals, saved logs, migration audits, and CI checks.

Pass a sequence of strings (lists and tuples are supported). The sequence is
copied and every item is type-checked before processing begins. Invalid inputs
raise `TypeError`, including an index for invalid items. Caller mutation during
processing does not change the selected inputs. Empty batches are accepted.

Validation batches require a schema object or boolean. Invalid schema-root
types raise `TypeError("schema must be an object or boolean")` before inputs
are copied or processed, including empty batches.

## Validate a Batch

```python
from outputguard import validate_batch

results = validate_batch(
    [
        '{"name": "Ada", "score": 1}',
        "{'name': 'Grace', 'score': 2}",
    ],
    schema,
    format="auto",
)

for item in results.results:
    print(item.index, item.valid, item.format)
```

The validation result includes:

- `results`: one result per input.
- `summary`: counts for valid, invalid, repaired, and failed items.

## Validate and Repair a Batch

An omitted format or `None` inherits the supplied guard's format; without a
guard, it uses JSON. An explicit override takes precedence. Unsupported formats
raise before processing any items, including when the input list is empty.
An empty string is an invalid override. Result metadata and summary counts keep
the selected spelling. See [format selection](formats.md#selecting-a-format).

Pass `repair=True` when each item should be repaired before the final schema
validation result is reported.

```python
results = validate_batch(outputs, schema, repair=True, format="json")
```

This is the batch equivalent of `validate_and_repair()`.

The guard's repair limit and strategy selection are checked before processing,
even for an empty batch. Changing a guard's limit to an invalid value raises
before any item reaches the guard. Validation without repair and `repair_batch()`
do not use the validation-repair loop's limit.

## Repair a Batch Without a Schema

```python
from outputguard import repair_batch

results = repair_batch(
    [
        '{"name": "Ada",}',
        "{name: 'Grace'}",
    ],
    format="json",
)

for item in results.results:
    print(item.index, item.text, item.parse_error)
```

The repair result includes repaired text and parse status for each item.

## Batch Summary

Summaries are computed after all results are collected. Strategy counts include
every occurrence in the final result metadata, including duplicate entries from
a custom guard. Format and strategy names are counted as exact strings.

`BatchSummary` contains:

- `total`: number of inputs.
- `valid`: number of valid or parseable outputs.
- `invalid`: number of failed outputs.
- `repaired`: number of outputs changed by repair.
- `parse_failures`: number of outputs that could not be parsed.
- `schema_failures`: number of parsed outputs that failed the schema.
- `success_rate`: valid divided by total, rounded to three decimals with ties
  rounded up (for example, 1/16 becomes `0.063`). An empty batch returns `0.0`.
- `strategy_counts`: repair strategy usage counts.
- `formats`: resolved format counts.

Repair and validity are independent: a repaired document that still fails its
schema contributes to both `repaired` and `schema_failures`. Parsed null values
rejected by the schema count as schema failures, not parse failures.

## Choosing a Format

Batch helpers inherit the format of a supplied guard when `format` is omitted
or `None`. Without a guard, they default to JSON. An explicit `format` overrides
the guard for that call without changing its configuration:

```python
from outputguard import OutputGuard, validate_batch

guard = OutputGuard(format="yaml")
validate_batch(["age: 42"], {"type": "object"}, guard=guard)
validate_batch(['{"age": 42}'], {"type": "object"}, guard=guard, format="json")
```

Use a specific format when every item should follow the same contract:

```python
validate_batch(outputs, schema, format="json")
```

Use `auto` when the source can contain mixed formats:

```python
validate_batch(outputs, schema, format="auto")
```

Auto detection is helpful for audits, but explicit formats are better for
production prompts because they make failures easier to interpret.

## CLI Input Shape

The batch CLI reads a JSON array of strings and validates each item against a
schema.

```json
[
  "{\"name\": \"Ada\",}",
  "{name: 'Grace'}"
]
```

Pass that file to `outputguard batch`:

```bash
outputguard batch outputs.json --schema schema.json --repair --input-format json
```

See [cli.md](cli.md) for flags and exit codes.

## Practical Workflows

Common batch workflows:

- Run nightly checks against saved model outputs.
- Validate prompt changes against an eval fixture.
- Repair historical logs before loading them into an analysis tool.
- Fail CI when a prompt fixture produces invalid structured data.

For CI, prefer explicit formats and schema validation.

