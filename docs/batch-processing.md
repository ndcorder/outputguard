# Batch Processing Guide

Batch processing is for validating or repairing many model outputs at once. It
is useful for evals, saved logs, migration audits, and CI checks.

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

Pass `repair=True` when each item should be repaired before the final schema
validation result is reported.

```python
results = validate_batch(outputs, schema, repair=True, format="json")
```

This is the batch equivalent of `validate_and_repair()`.

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

`BatchSummary` contains:

- `total`: number of inputs.
- `valid`: number of valid or parseable outputs.
- `invalid`: number of failed outputs.
- `repaired`: number of outputs changed by repair.
- `parse_failures`: number of outputs that could not be parsed.
- `schema_failures`: number of parsed outputs that failed the schema.
- `success_rate`: valid divided by total, rounded to three decimals.
- `strategy_counts`: repair strategy usage counts.
- `formats`: resolved format counts.

## Choosing a Format

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

