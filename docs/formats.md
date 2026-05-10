# Formats Guide

OutputGuard started with JSON. Version 2.0 keeps JSON as the default while
adding explicit support for other structured formats that LLMs commonly emit.

## Supported Formats

| Format | `format` values | Typical use |
| --- | --- | --- |
| JSON | `"json"` | API payloads, tool calls, eval fixtures |
| YAML | `"yaml"`, `"yml"` | Human-readable configs and long model outputs |
| TOML | `"toml"` | Config files and package metadata snippets |
| Python literal | `"python-literal"`, `"python"`, `"py"`, `"literal"` | Python dict/list/tuple output from models |
| Auto | `"auto"` | Mixed-format input where the format is unknown |
| Forced JSON off | `"forced-json-off"`, `"forced_json_off"` | Prompts that explicitly prohibit JSON |

## JSON Is Still the Default

These calls are equivalent:

```python
validate_and_repair('{"name": "Ada"}', schema)
validate_and_repair('{"name": "Ada"}', schema, format="json")
```

Use an explicit `format` when a prompt asks for a non-JSON output format or
when you are validating saved model output from a mixed-format source.

## JSON

JSON repair handles common LLM mistakes such as:

- Trailing commas.
- Single quotes.
- Unquoted object keys.
- Markdown code fences.
- Text before or after the JSON payload.

```python
from outputguard import validate_and_repair

result = validate_and_repair("{name: 'Ada', score: 1,}", schema, format="json")
```

## YAML

YAML validation parses YAML into Python data. Repair focuses on extracting the
structured block and normalizing common wrapper issues.

```python
result = validate_and_repair(
    """
    ```yaml
    name: Ada
    score: 1
    ```
    """,
    schema,
    format="yaml",
)
```

## TOML

TOML support is useful when models generate configuration fragments.

```python
result = validate_and_repair(
    """
    name = "Ada"
    score = 1
    """,
    schema,
    format="toml",
)
```

## Python Literals

Python literal support accepts safe literal syntax such as dicts, lists, tuples,
strings, numbers, booleans, and `None`.

```python
result = validate_and_repair(
    "{'name': 'Ada', 'score': 1, 'tags': ['math', 'systems']}",
    schema,
    format="python-literal",
)
```

This mode is for data literals, not executable Python code.

## Auto Detection

Use `format="auto"` when you do not know the format in advance.

```python
result = validate_and_repair("name: Ada\nscore: 1\n", schema, format="auto")
```

Auto detection tries supported formats and records the resolved format in the
result. Prefer an explicit format when you control the prompt because explicit
formats produce more predictable feedback.

## Forced JSON Off

Use `format="forced-json-off"` when your prompt explicitly says not to return
JSON. This makes intent clear in code and prevents a later reader from assuming
JSON repair is appropriate.

```python
result = validate_and_repair(model_output, schema, format="forced-json-off")
```

This mode is especially useful when a model is asked for YAML, TOML, or another
non-JSON structured response and may include explanatory text.

## Schema-Free Repair

When you do not have a schema, use `repair()` instead of a validation API.

```python
from outputguard import repair

result = repair("{name: 'Ada', score: 1,}", format="json")
print(result.text)
```
