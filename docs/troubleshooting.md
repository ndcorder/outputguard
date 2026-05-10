# Troubleshooting

This guide maps common symptoms to the fastest useful fix.

## The Model Returned Markdown Fences

Use repair:

```python
result = outputguard.validate_and_repair(raw, schema)
```

Markdown fences are a normal model behavior and are handled by repair
strategies.

## The Output Is Parseable but Missing a Field

Repair cannot invent missing values. Use the validation errors to retry:

```python
if not result.valid:
    prompt = outputguard.retry_prompt(raw, schema, result.errors)
```

The retry prompt explains which field is missing.

## The Retry Prompt Is Too Large

Omit the previous model output:

```python
prompt = outputguard.retry_prompt(
    raw,
    schema,
    result.errors,
    include_message_history=False,
)
```

For guarded generation:

```python
result = outputguard.guarded_generate(
    prompt=prompt,
    schema=schema,
    generate=generate,
    include_message_history=False,
)
```

## The Retry Prompt Repeats Sensitive Output

Use `include_message_history=False` or the CLI flag:

```bash
outputguard retry-prompt response.txt --schema schema.json --no-message-history
```

OutputGuard cannot classify sensitive data for you. Choose this option when
your application already stores the prior output elsewhere or should avoid
re-sending it to the model.

## YAML Looks Valid but Fails JSON Parsing

Pass the format explicitly:

```python
result = outputguard.validate_and_repair(raw_yaml, schema, format="yaml")
```

JSON is the default for backward compatibility.

## Auto Detection Picks an Unexpected Format

Use an explicit format when you control the prompt:

```python
result = outputguard.validate_and_repair(raw_toml, schema, format="toml")
```

`auto` is best for historical or mixed input where you do not know the format in
advance.

## `parse()` Raises

`parse()` is intentionally strict. If you want to inspect errors without
raising, use:

```python
result = outputguard.validate_and_repair(raw, schema)
```

Then inspect `result.errors`, `result.data`, and `result.repaired_text`.

## CLI Exits With Code 1

Exit code `1` means validation or repair failed. Use JSON output for details:

```bash
outputguard validate response.txt --schema schema.json --repair --format json
```

Exit code `2` means the command arguments or input shape were invalid.

## Batch Results Have `schema_failures`

Those items parsed successfully but did not match your schema. Inspect each
item's `errors` list to decide whether to retry the model or change the schema.

## Repair Does Nothing

Possible causes:

- The output is already parseable.
- The problem is semantic, not syntax.
- The selected format is wrong.
- The output is too malformed for repair and needs a retry.

When in doubt, validate first and inspect the errors.

