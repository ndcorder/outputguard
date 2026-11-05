# Formats Guide

OutputGuard started with JSON. Version 2.0 keeps JSON as the default while
adding explicit support for other structured formats that LLMs commonly emit.

A schema's `format` keyword (for example, `email`) validates parsed values.
The API's `format` argument selects the parser described here. See
[schema format assertions](api.md#schema-format-assertions).

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

## Selecting a Format

An omitted format or `None` inherits the guard's setting. Without a guard, it
selects JSON. JavaScript accepts an omitted format or `null` for the same
behavior. A per-call format takes precedence and leaves the guard unchanged.
An empty string is an unsupported format; it does not select the default.

Names are case-insensitive and trim the same surrounding whitespace in both
ports, using [ECMAScript's trimming rules](https://tc39.es/ecma262/#sec-trimstring).
This includes a BOM and Unicode space separators, and excludes NEL and control
separators. Whitespace inside a name is preserved and makes it unsupported.

Results, repair reports, generation results, and batch format counts preserve
the selected spelling, including aliases, case, and surrounding whitespace.
Constructing a guard validates its default format. Batch helpers validate the
selected format even for an empty input list, and generation validates it before
calling the provider. Unsupported names raise a configuration error rather than
a document parse failure; non-string selections raise `TypeError`.

## JSON

JSON rejects bare `NaN`, `Infinity`, and `-Infinity`, including in Python.
`validate()` reports these as parse failures. With repair enabled, `fix_values`
replaces them, `undefined`, and signed variants (`+Infinity`, `+NaN`, `-NaN`)
with `null`. The repaired data must still satisfy the schema: a number-only
property rejects a repaired `null` as a schema failure.

Quoted spellings remain strings. `fix_values` and `fix_booleans` replace only
complete bare values and preserve JSON escapes, including strings ending in
backslashes. Ordinary JSON number syntax uses the native parser's range and
precision; an exponent such as `1e400` can still overflow to infinity.

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

YAML uses an explicit 1.2 core profile for values. Plain `yes`, `on`, dates,
numeric underscores, and sexagesimal numbers remain strings. `0123` is decimal
123; `0o123` is octal 83. Core boolean and null spellings resolve normally,
and quoted scalars stay strings. `.inf` and `.nan` remain native floating-point
values. Physical CR and CRLF normalize to LF; NEL, line separators, and
paragraph separators remain data.

Mapping keys use their decoded scalar text: `true`, `01`, and `1` are distinct
string keys. Empty keys are supported. Duplicate decoded keys fail parsing,
including quoted/escaped duplicates. Collection keys, alias keys, and explicit
non-string key tags are rejected. Prototype names such as `__proto__` remain
ordinary own properties.

Only one document is accepted. A `%YAML 1.2` directive is allowed; other versions
and unknown directives fail parsing. Supported explicit tags are `!!str`,
`!!null`, `!!bool`, `!!int`, `!!float`, `!!seq`, and `!!map`, with strict scalar
contents, plus the non-specific `!` tag. Custom tags and extended binary,
timestamp, set, pairs, and ordered-map tags are rejected. `<<` is an ordinary
string key; merge semantics are disabled.

Backward aliases preserve shared-container identity. Undefined aliases,
duplicate anchors, and cycles fail parsing. Expanded value weight must be at
most 100 times source weight. A scalar weighs one plus its decoded UTF-16
length; a container or source alias reference weighs one. Expansion replaces
each alias reference with its complete target weight. This allows large,
harmless alias lists while rejecting exponential amplification.

Both ports use the same parser and profile. Python runs a bundled copy through
the existing QuickJS-NG dependency, with lazy thread-local contexts reset after
a fork; Node is not required at runtime. Python constructs its own integers and
floats from numeric source text. JavaScript uses `Number`, so native numeric
precision, range, and runtime resource limits still apply.

This changes the earlier Python YAML 1.1 defaults: `yes`/`on` and dates no
longer become booleans or date objects, and duplicate keys no longer overwrite
earlier values. Use `true`/`false` when the schema requires booleans. Other
applications' YAML parsers and global defaults remain unchanged.

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

Both ports use the same private TOML 1.1 parser. Dates and times become strings
so JSON Schema can apply `type: "string"`, `format`, `pattern`, and `const`, and
CLI JSON output can serialize them directly. For example,
`stamp = 2026-11-04t12:34:56.123456789z` produces
`{"stamp": "2026-11-04T12:34:56.123456789Z"}`.

Date strings preserve all fractional digits and the authored numeric offset,
including `+00:00` and `-00:00`. The delimiter becomes `T`, UTC becomes `Z`, and
omitted seconds become `:00`. Local dates/times remain local; no timezone
conversion occurs. Gregorian calendar and clock fields are checked without
native date-object rollover or precision loss. Year `0000` is accepted. Leap
second `:60` requires 23:59 UTC in the authored offset, or 23:59 for local time;
the profile does not consult historical leap-second tables.

TOML 1.1 supports omitted seconds, `\e` and `\xHH` escapes, and comments,
newlines, and a trailing comma in inline tables. Bare keys remain ASCII; quote
Unicode keys. CRLF source newlines normalize to LF, including inside multiline
strings. Bare carriage returns, invalid Unicode, duplicate keys, and table
redefinitions are parse failures. Quoted date-like strings remain literal.

Python runs the bundled parser through thread-local QuickJS-NG contexts and
needs no Node installation. Integers remain exact Python integers, and floats
retain native floating-point behavior, including non-finite values. JavaScript
uses `Number` and rejects integers outside `±9007199254740991` rather than
rounding them. That numeric range difference also applies in auto mode.

This replaces Python's `tomllib`/`tomli` date objects and JavaScript's
`TomlDate` objects. Code that needs date objects should convert the returned
strings explicitly. The standalone `tomli` runtime dependency is removed, and
other applications' native parsers remain unchanged.

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

Both ports support single, double, and triple quotes; `r`/`R` raw strings;
`u`/`U` strings; and adjacent string literals. Ordinary strings decode Python's
simple escapes, octal escapes (up to three digits), `\x` (two hex digits),
`\u` (four), and `\U` (eight). Unknown escapes preserve their backslash.
Physical line continuations disappear in ordinary strings and remain in raw
strings. Physical CRLF and CR line endings normalize to LF. Unescaped newlines
require triple quotes. Comments and line joining work between literal tokens;
parentheses allow adjacent strings on multiple lines and group a single value.

Real numbers accept decimal integers, `0b` binary, `0o` octal, `0x` hexadecimal,
and decimal floats with optional scientific notation. Base prefixes are
case-insensitive and allow one underscore before the first digit (`0x_2A`).
Other underscores must separate digits. Decimal integers with leading zeros
must be all zeros; floats such as `01.` and `1.e2` are valid. One unary `+` or
`-` may precede whitespace and grouped operands (`- (0x_2a)`). Real-number
arithmetic and repeated signs are rejected. `-0` is integer zero; `-0.0`
retains its negative floating-point sign.

Python preserves integer precision; JavaScript uses `Number` for every numeric
form, including binary, octal, and hexadecimal. Large integers can round or
overflow in JavaScript. Floating-point overflow and underflow retain native
behavior, including infinity and signed zero. Decimal-integer literal length
limits can also depend on the Python runtime's configuration.

Python uses `ast.literal_eval`; JavaScript implements a subset. Named Unicode
escapes (`\N{...}`) work in Python but produce a parse error in JavaScript;
use `\u` or `\U` for portable text. Bytes, sets, and complex numbers also fall
outside the JavaScript subset. For portable data, use string dictionary keys,
lists, and JSON-compatible scalar values. Tuples retain their native Python
type and become arrays in JavaScript, so array-schema checks can differ.

## Auto Detection

Use `format="auto"` when you do not know the format in advance.

```python
result = validate_and_repair("name: Ada\nscore: 1\n", schema, format="auto")
```

Auto detection tries JSON, TOML, Python literals, then YAML. Results and batch
format counts keep the selected format string, including alias spellings such
as `forced-json-off`. Prefer an explicit format when you control the prompt
because explicit formats produce more predictable feedback.

Non-JSON formats retain their own syntax. For example, bare `NaN` in `auto`
mode falls through JSON parsing and becomes a YAML string; it is not repaired
to `null`. YAML `.nan`/`.inf` and TOML `nan`/`inf` remain native numeric values.

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
