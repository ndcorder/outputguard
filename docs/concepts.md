# Concepts

OutputGuard is easiest to use when you separate four jobs: parsing, validation,
repair, and retry. Each API combines those jobs differently.

## Structured Text vs Parsed Data

LLMs return text. Your application usually needs data.

```text
LLM text -> parser -> Python data -> JSON Schema validator -> application
```

OutputGuard repairs and validates around that boundary. It does not replace your
business rules or database constraints.

## Parsing

Parsing turns text into Python data. A parse failure means the output is not
valid syntax for the selected format.

Examples:

- JSON with trailing commas fails strict JSON parsing.
- YAML with an unterminated list fails YAML parsing.
- Python literal mode accepts `True`, `False`, and `None`, but not executable
  Python code.

## Validation

Validation checks parsed data against a JSON Schema.

```python
result = outputguard.validate(raw, schema)
```

If parsing succeeds but the schema fails, `result.data` contains parsed data and
`result.errors` describes schema problems. If parsing fails, `result.data` is
`None` and the error is attached to `$`.

## Repair

Repair fixes common syntax problems in model output. It is useful for issues
such as markdown fences, comments, trailing commas, single quotes, unquoted
keys, Python booleans, truncated closers, and extra text around a payload.

Repair does not invent missing business data. If the model omitted a required
field, OutputGuard can explain the schema error, but the model needs to provide
the missing value.

## Validate and Repair

`validate_and_repair()` is the default application workflow:

1. Parse and validate the original output.
2. If it fails, apply repair strategies.
3. Validate the repaired output.
4. Return a `ValidationResult` either way.

Use it when minor syntax mistakes should be fixed automatically.

## Parse or Raise

`parse()` is the strict convenience path. It validates, repairs if needed, then
returns parsed data or raises a package exception.

Use it when the caller cannot continue without valid data.

## Retry Prompts

`retry_prompt()` turns validation errors into feedback for the model. By
default, the generated prompt includes:

- A short instruction.
- Numbered validation errors.
- A schema summary.
- The previous model output.
- A final "return only corrected output" instruction.

Set `include_message_history=False` to omit the previous model output. This is
useful when output is large, sensitive, or already stored elsewhere in your chat
history.

## Guarded Generation

`guarded_generate()` manages a whole retry loop:

```text
prompt -> model -> validate/repair -> success
                         |
                         v
                  retry prompt -> model
```

You still own the model client. OutputGuard only calls the function you provide
and validates the returned text.

## Formats

JSON is the default. Other formats are explicit:

- `format="yaml"`
- `format="toml"`
- `format="python-literal"`
- `format="auto"`
- `format="forced-json-off"`

Use explicit formats for production prompts. Use `auto` when processing mixed
historical output.

## Batch Processing

Batch APIs apply the same validation or repair workflow to many outputs and
summarize the result. Use them for evals, logs, regression fixtures, and CI.

