# API Guide

This guide lists the public functions most users need. Import from
`outputguard` unless you are working inside the package.

```python
from outputguard import (
    validate,
    repair,
    validate_and_repair,
    parse,
    retry_prompt,
    guarded_generate,
    guarded_generate_async,
    validate_batch,
    repair_batch,
)
```

## Choosing an API

| Use case | Function |
| --- | --- |
| Validate one output against a JSON Schema | `validate()` |
| Validate, repair if needed, then validate again | `validate_and_repair()` |
| Repair syntax without a schema | `repair()` |
| Parse valid schema-matching data or raise | `parse()` |
| Build a retry prompt from validation errors | `retry_prompt()` |
| Wrap a sync LLM generation callable | `guarded_generate()` |
| Wrap an async LLM generation callable | `guarded_generate_async()` |
| Validate many outputs against one schema | `validate_batch()` |
| Repair many outputs without a schema | `repair_batch()` |
| Update a reused schema after editing it | `invalidate_schema()` |

## Minimal Schema Example

Validation APIs accept a JSON Schema dictionary or a boolean schema. The
exported `Schema` type describes both forms.

The root must be a `dict` (including real subclasses) or `bool`. Other values,
including `None`, numbers, strings, arrays, and objects that pretend to be
dictionaries, raise `TypeError("schema must be an object or boolean")` without
coercion. Validation checks this before parsing, even when document text is
malformed. Batch validation checks before reading or processing items,
including empty batches; guarded generation checks before provider or observer
calls, with repair enabled or disabled. Retry prompts check the root type too.

This check only covers the root's type. Schema keywords and reference behavior
remain with the existing validation engine. Arrays inside schema annotations or
keywords are not rejected by the root check. `True`, `False`, and `{}` are valid
roots; `False` reports schema failure rather than a configuration error.

```python
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["name", "score"],
}
```

`True` accepts any successfully parsed value; `False` rejects every value as a
schema failure. Parsing is still required in both cases. These schemas work
with validation, repair, strict parsing, batch helpers, guarded generation, and
JSON schema files supplied to the CLI.

Boolean subschemas can allow or forbid individual properties or array items:

```python
schema = {"type": "object", "properties": {"debug": False, "metadata": True}}
result = validate('{"debug": 1}', schema)
print(result.errors[0].path)  # $.debug
```

## Text Inputs

Text-processing functions accept `str` instances and their real subclasses,
including empty strings. Numbers, booleans, `None`, binary buffers, arrays,
mappings, and other stringifiable objects raise `TypeError("text must be a string")`. Inputs are not coerced, decoded, or
trimmed. Pass document text, or explicitly serialize/decode a value first.
An actual string containing invalid syntax still produces the usual parse
failure; an accepted `"null"` still returns `None` as parsed data.

Guarded generation requires a string `prompt`, checked before invoking the
provider or observer. This applies when repair is disabled too. Non-string
provider results retain the `generate must return a string` error. The async
wrapper accepts strings and supported awaitables that resolve to strings.

Batch helpers accept a sequence of strings, such as a list or tuple. A bare
string, binary buffer, set, or iterator is not a batch. The sequence is copied
and every item is checked before any validation or repair begins. Invalid
containers raise `TypeError("texts must be a sequence of strings")`; invalid
items identify their zero-based index, for example `texts[1] must be a string`.
An empty sequence is accepted. Mutating the original sequence during processing
does not change the selected inputs.

Retry prompts require string text even when message history is disabled.

## Strategy Selection

Configure a guard with exact, case-sensitive strategy names:

```python
from outputguard import OutputGuard

guard = OutputGuard(strategies=("fix_commas", "strip_fences", "fix_commas"))
print(guard.strategy_names)  # ['strip_fences', 'fix_commas']
```

`None` selects all registered strategies. An empty sequence disables repair.
Names execute once in registry order, regardless of the order supplied. Lists
and tuples are accepted; strings, sets, generators, non-string elements, and
unknown names are rejected. Names are not trimmed or case-normalized by the API.

The constructor validates and copies the selection. Changing the caller's list
or the fresh list returned by `strategy_names` does not change the guard.
Invalid types raise `TypeError`; unknown names raise `ValueError`. Repair paths
check configuration even for valid documents, zero repair attempts, and empty
batches. Guarded generation checks before calling the provider when repair is
enabled. Validation without repair does not consult strategy selections.

## Formats

Most APIs accept a `format` argument. The default is `"json"`.

With a guard, an omitted format or `None` inherits its setting. An explicit
override is validated and preserved in metadata; an empty string is invalid.
See [format selection](formats.md#selecting-a-format) for aliases and trimming.

Supported values:

- `"json"`
- `"yaml"` or `"yml"`
- `"toml"`
- `"python-literal"`, `"python"`, `"py"`, or `"literal"`
- `"auto"`
- `"forced-json-off"` or `"forced_json_off"`

See [formats.md](formats.md) for detailed behavior.

JSON rejects bare `NaN` and `Infinity` as parse failures. Repair maps these
values to `null`, then checks the schema again. Quoted spellings remain strings;
other formats retain their own parsing rules.

YAML uses the shared [1.2 core profile](formats.md#yaml), with string mapping
keys and strict core tags. Duplicate keys, unsupported tags, cyclic aliases,
and excessive alias expansion are parser failures before schema validation.

## `validate()`

Use this when you only need a validity check.

```python
from outputguard import validate

result = validate('{"name": "Ada", "score": 1}', schema)

if result.valid:
    print(result.data)
else:
    for error in result.errors:
        print(error.path, error.message)
```

`validate()` returns a `ValidationResult` with:

- `valid`: whether the parsed data matches the schema.
- `data`: parsed Python data when parsing succeeds.
- `parse_error`: parser diagnostic on a parse failure, otherwise `None`. Use
  this field to distinguish parse failures from schema failures; `data=None`
  can also be a successfully parsed JSON/YAML null or Python `None`.
- `errors`: validation or parse errors.
- `repaired`: always `False` for validate-only calls.
- `strategies_applied`: repair strategies used, if any.
- `original_text`: input text.
- `repaired_text`: repaired text, if any.
- `format`: resolved input format.

### Validation errors

Each error has a `message`, `path`, `schema_path`, and `value`. The `value` is
the instance rejected by that constraint; for a missing required property, it
is the containing object.

Instance paths use dot notation for simple ASCII identifiers, numeric brackets
for array indexes, and JSON-quoted brackets for other property names:

| Location | `path` |
| --- | --- |
| An ordinary property | `$.age` |
| An array item | `$.items[0]` |
| An object property named `"0"` | `$["0"]` |
| A property containing a dot or slash | `$["a.b"]`, `$["a/b"]` |
| An empty property name | `$[""]` |

Quotes, backslashes, and control characters inside a property name are escaped
as JSON strings. Python `schema_path` uses the same path notation to locate the
constraint in the schema. JavaScript `schemaPath` retains Ajv's JSON Pointer
notation. Validator messages and schema paths may therefore differ across the
two implementations.

Literal `__proto__` entries in `properties` and `patternProperties` enforce
their constraints like other keys in both ports. They also count as declared
properties for `additionalProperties`. The JavaScript port prepares these
schemas without changing caller-owned objects or local references, including
references within nested `$id` resources. Reuse schema objects as immutable
values so the JavaScript port can cache their compiled validators.

### Updating a reused schema

Keep a reused schema immutable between explicit invalidations. After editing
its contents, call `invalidate_schema(root)` with the root passed to validation.
This applies to edits inside properties, arrays, referenced definitions, and
literal reference targets. Invalidate every root that uses an edited child.
All guards using that same root observe the update on subsequent validation.

```python
from outputguard import invalidate_schema, validate

schema = {"type": "integer"}
assert validate("1", schema).valid
schema["type"] = "string"
invalidate_schema(schema)
assert validate('"ready"', schema).valid
```

Python reads the current schema on every validation. `invalidate_schema()`
checks its root type and provides the same API for portable workflows.

Invalidation marks the root for reuse; it preserves the supplied object and
returns `None`. Calls are safe before first use and may be repeated, including for
boolean roots. Invalid root types raise `TypeError`. Keyword checks and
reference resolution happen when the schema is used for validation.

Literal comparisons for `const`, `enum`, and `uniqueItems` treat object keys
such as `constructor`, `toString`, `valueOf`, and `__proto__` as data. Property
order does not affect equality, and booleans remain distinct from numbers.
Duplicate strings named `"__proto__"` are also rejected by `uniqueItems`.

### Schema format assertions

A schema's `format` keyword checks parsed values in both ports. This differs
from the API's `format` argument, which selects the document parser. Invalid
format values are schema failures, including after syntax repair. Unknown
format names are ignored. Add an explicit `type` when the value must have a
particular JSON type; string formats ignore non-strings and numeric formats
ignore non-numbers, including booleans.

| Formats | Checks |
| --- | --- |
| `date`, `time`, `date-time` | Calendar dates, clock ranges, time zones, and leap seconds at UTC 23:59 |
| `iso-time`, `iso-date-time` | The same clock/date checks with an optional time zone |
| `email`, `hostname`, `ipv4`, `ipv6` | ASCII email/host syntax and IP address syntax |
| `uri`, `uri-reference`, `uri-template`, `url` | Full URIs, relative references, templates, and legacy public HTTP/FTP URLs |
| `uuid` | Hyphenated UUIDs, optionally prefixed with `urn:uuid:` |
| `json-pointer`, `json-pointer-uri-fragment`, `relative-json-pointer` | Pointer syntax and escape sequences |
| `duration`, `byte` | Integer ISO duration components and Base64 text |
| `int32`, `int64` | Signed integer ranges; parser precision still applies |
| `float`, `double`, `password`, `binary` | Accepted hints without extra range/content constraints |
| `regex` | ECMAScript regular-expression syntax (without the Unicode flag) |

Date-time separators may be `T`, `t`, or a single space. Time zones accept `Z`
or signed hours with optional minutes (`+05`, `+0530`, `+05:30`). All checks
consume the complete value; a final newline is not silently discarded. Pointer
strings may contain newlines where their grammar permits them. Base64 input
must be one complete encoded string. Format checking performs no network or
email-delivery checks.

Python's checker has no optional format dependencies and does not change native
`jsonschema` registrations. JavaScript changes only its owned Ajv compilers.
The format pattern data is adapted from `ajv-formats` under its MIT license,
included in both packages.

### Regular expressions

Both ports use ECMAScript matching for `pattern`, `patternProperties`, and
additional-property discovery. Python embeds QuickJS-NG; JavaScript uses its
native engine. Named groups (`(?<name>...)`), lookbehind, Unicode property
escapes, ASCII `\d`/`\w`, UTF-16 surrogates, and line terminators therefore
follow JavaScript semantics. Python-specific syntax such as `(?P<name>...)`
must be changed to ECMAScript syntax. Unrelated `jsonschema` validators and
Python's `re` module keep their normal behavior.

`pattern` and `patternProperties` use the Unicode (`u`) flag, matching Ajv's
default. The `regex` format checks the default RegExp grammar without `u`, so
some legacy escape sequences accepted by the format are invalid in a schema's
`pattern`. Schema patterns search for a match; add `^` and `$` to require the
whole string. In ECMAScript, `$` without multiline mode requires the actual
end of the string, including when the value ends in a newline.

Property patterns compile independently, including their capture groups.
An empty property pattern matches every key. Pattern matches also declare keys
for `additionalProperties`; they retain normal instance and schema diagnostics.
Lone surrogates in property paths are escaped as well-formed JSON.

Python creates an engine only when a regex is first used. Each thread has its
own context and a cache of at most 128 compiled pattern/flag pairs. A forked
child creates a new context. Input strings cross the engine boundary as JSON
data; they are never evaluated as JavaScript source. No Node.js executable or
worker thread is required. Available syntax, Unicode property tables, and
resource limits can vary by engine version. Use features available on your
oldest supported JavaScript runtime.

### Numeric constraints

`multipleOf` accepts decimal multiples such as `0.3` of `0.1` and `2.01` of
`0.01`. Whole-number values use exact integer arithmetic; fractional values use
their decimal representations. There is no tolerance: `0.30000000000000004` is not
a multiple of `0.1`. Finite values with extreme exponents work without dividing
floating-point numbers. See [Draft 7 multipleOf](https://json-schema.org/draft-07/draft-handrews-json-schema-validation-01#rfc.section.6.2.1).

These checks preserve parsed data, schema values, literal `const`/`enum`
comparisons, and ordinary numeric error locations. Non-number values are
unaffected by `multipleOf`; add `type: "number"` to require numeric input.
Normal parser precision still applies: Python preserves integer precision,
while JavaScript uses `Number`. Fractional floating-point values use their
canonical decimal representations. Validation cannot recover digits already lost while
parsing or constructing a number.

### References and dependencies

Schema IDs belong to the supplied document. Independent schemas may reuse the
same root or nested `$id`, including with different constraints. Validating a
schema does not register its IDs for later calls or other guards. Include
shared resources in each document, for example under `definitions`.

Resource discovery follows Draft 7 schema locations, including `definitions`,
`properties`, schema dependencies, and applicator subschemas. An `$id` inside
an unknown annotation, a literal value, or a later-draft keyword such as `$defs`
does not declare a resource. Explicit JSON Pointers can still select those
contents as schemas. The selected annotation's own `$id` does not change the
pointer's scope; IDs on its schema descendants can affect relative resolution
without registering those descendants as resources.

Draft 7 ignores `$anchor` and `$dynamicAnchor`. Legacy plain-name fragments
such as `"$id": "#part"` remain available as anchors. Nonfragment `$id` values
beside `$ref` are ignored. Empty IDs and pointer fragments such as `#/part`
do not replace the document or override actual JSON Pointer targets.

Relative IDs such as `constructor`, `toString`, and `__proto__` are valid
resource names. JSON Pointer references resolve only properties present in the
schema document; they cannot select inherited JavaScript properties. Explicit
schema properties with those names remain valid reference targets.

References may URI-encode the leading pointer separator or characters in a
valid plain-name anchor. For example, `#%2Fdefinitions%2Fpart` selects `#/definitions/part`, and
`#%70art` references the plain-name anchor declared by `"$id": "#part"`.
Plain-name IDs start with a letter, followed by letters, digits, hyphens,
underscores, colons, or periods, as specified by [Draft 7](https://json-schema.org/draft-07/draft-handrews-json-schema-01#rfc.section.8.2.3).

Escape pointer tokens with `~0` for `~` and `~1` for `/` before URI encoding.
A literal token `%2F` therefore appears as `%252F`; it is decoded once and
remains distinct from a slash. Resources declared under percent-named schema
keys remain addressable by ID and by pointer. Encoded references preserve
embedded scopes, recursion, literal data, and false-schema instance locations.
See [JSON Pointer URI encoding](https://www.rfc-editor.org/rfc/rfc6901#section-6).

Array tokens use `0` or ASCII digits without a leading zero. Tokens such as
`01`, `-1`, `+1`, and `-` raise a reference lookup error when selecting an array
element. These spellings remain valid literal object keys. Index syntax is
checked after URI decoding; missing or out-of-range indexes also fail lookup.
See [JSON Pointer evaluation](https://www.rfc-editor.org/rfc/rfc6901#section-4).

A reference target must be an object or boolean schema. Selecting `null`, a
number, a string, or an array raises a reference lookup error. Pointers can
traverse arrays to reach schemas, but cannot continue through scalars or
booleans. Object and boolean values inside annotations remain valid targets;
their original literal contents remain available for `const` and `enum`.

Subschemas under `if`, `contains`, `not`, and `oneOf` apply their own `$id` to
relative references, including inside nested resources and explicit Draft 7
declarations. A failed applicator can expose different numbers of diagnostic
details in the two native validators; validity and resource scopes agree.

The non-standard `$async` field is ordinary metadata in both ports. Validation
returns a synchronous result with a boolean `valid` field, including when that
metadata appears in nested or referenced schemas. Its value remains available
to JSON Pointer references such as `#/$async`. Literal `const`, `enum`, and
`default` values retain their original contents when annotations are prepared.

Schemas selected from literal values through `$ref` enforce their constraints
like other subschemas, including prototype-named keys and reference sibling
rules. False subschemas retain their instance locations when reached through
literal values, nested resources, and recursive references. Comparing a literal
as `const` or `enum` data preserves its original contents.

Both ports use Draft 7 reference semantics: assertions alongside `$ref`, such
as `type`, `properties`, or `dependencies`, are ignored. Sibling locations stay
available as reference targets. Use `allOf` to combine a reference with more
constraints:

```json
{
  "definitions": {"id": {"type": "integer"}},
  "allOf": [{"$ref": "#/definitions/id"}, {"minimum": 1}]
}
```

`dependencies` applies when the trigger property is present, including when
its value is null, false, or empty. A property dependency requires the listed
properties; a schema dependency validates the containing object. Trigger names
such as `__proto__` and `constructor` behave like ordinary keys.
Property lists, boolean schemas, and object schemas may share one dependency
map in any order. Resource IDs in schema dependencies remain discoverable
regardless of which kind appears first.

Map keys retain their literal meaning, including dependency triggers named
`$id` or `$ref`. A map's member named `$id` does not set the map's URI scope.
Real subschemas named `properties`, `definitions`, `dependencies`, `enum`, or
`patternProperties` still apply their own `$id` values to relative references.
Pointers through `items` and `dependencies` preserve this distinction between
schemas, maps, and annotation data, including when selecting a whole map as a
schema. Literal `const` and `enum` values remain unchanged.

Retry summaries omit ignored `$ref` siblings and label referenced property
schemas as `referenced schema`. Validation errors provide the feedback for
constraints reached through references.

## `validate_and_repair()`

Use this for the common path: validate one model output, repair it when needed,
and validate the repaired output against the same schema.

```python
from outputguard import validate_and_repair

result = validate_and_repair("{name: 'Ada', score: 1,}", schema, format="json")

print(result.valid)
print(result.data)
print(result.repaired)
print(result.strategies_applied)
```

If the original text is already valid, no repair is applied. If repair succeeds,
`repaired=True` and `repaired_text` contains the repaired payload.

Syntax repair can succeed while schema validation still fails. In that case,
`valid=False` and `repaired=True`; `data`, `errors`, and `repaired_text` describe
the repaired document, and `original_text` retains the original input. Retry
prompts can then target the remaining schema errors. Already parsed documents
skip syntax repair, and repair stops when it cannot change the text.

## `repair()`

Use this when you want schema-free syntax repair.

```python
from outputguard import repair

result = repair("{'name': 'Ada', 'active': True}", format="python-literal")

print(result.repaired)
print(result.text)
print(result.parse_error)
```

`repair()` returns a `RepairResult` with:

- `repaired`: whether changed text was accepted as parseable.
- `text`: the accepted repaired text, or the original text if repair failed.
- `strategies_applied`: names of strategies used by an accepted repair; empty on failure.
- `parse_error`: parser error when repair cannot produce parseable data.
- `format`: resolved input format.

Pass `report=True` to return `(RepairResult, RepairReport)` directly:

```python
result, report = repair("{name: 'Ada'}", report=True)
print(report.candidate_text)
print(report.strategies_tried)
```

Omitting `report` or passing `False` returns only `RepairResult`. The flag is
keyword-only; the positional `format` argument remains supported. An
`OutputGuard` instance accepts the same report flag with its configured format
and strategies. Type annotations distinguish literal flags; a runtime boolean
returns the union of the plain result and report tuple.

Failed repairs preserve the original input instead of returning partial edits.
The parser diagnostic describes the last candidate attempted. Use
`report.candidate_text` to inspect that candidate; `report.final_text` matches
the returned `result.text`. The report's `steps` describe the accepted pass, or
the final attempted pass on failure. Earlier discarded passes are not retained.
Each step records its input/output text, `changed`, and `error` (`None` for no
error). `report.strategies_applied` lists changes within those recorded steps,
including discarded changes when repair fails. `report.diff` compares the
original and returned text, so it is empty after a failed repair.

Strategies run synchronously and must return strings. If a strategy raises an
ordinary exception or returns another type, its text stays unchanged, its error
is recorded, and later strategies can still repair the document. Fresh coroutine
returns are closed; suspended coroutines remain with their owner. Process and
cancellation exceptions propagate. `report.step_diffs()` includes strategy
errors as well as text changes, even when a failed step made no change.

Confidence uses the number of changed steps and the change in Unicode code-point
length. It rounds to two decimal places using exact half-up rounding, returns
zero for failed repairs, and is a heuristic rather than a probability.

`report.diff` and `step.diff` return unified patches with hunk ranges and up to
three context lines. Nonempty patches end in LF and include
`\ No newline at end of file` markers where needed. Lines split only at LF:
CRLF bytes, bare CRs, and Unicode separators remain in the payload. Labels are
`original` / `repaired` or `before_NAME` / `after_NAME`; unusual strategy names
are quoted and escaped. Supply a target file or real path labels when applying
a patch with a patch tool.

Both ports use the same deterministic bounded matcher. It trims shared prefixes
and suffixes first. Empty sections, a single mismatched line on each side, and
sections with no shared lines are emitted directly as replacements. Other
sections search for a shortest edit path. Search stops at 256
insertions/deletions or a combined one million frontier steps and line comparisons.
If either limit is exceeded, the unmatched middle is rendered as a complete
replacement. The patch still reconstructs the exact output; it can include
unchanged interior lines when the limit is reached.
This bounds search work and trace memory for dissimilar or repetitive output.
Report diffs are empty for identical texts. Strategy diffs are also empty for
a step marked unchanged.

### Markdown fences

`strip_fences` selects the first wrapper outside quoted strings, structured
containers, and comments. Literal fenced code inside a JSON value remains part
of that value; other strategies can repair its surrounding keys or raw line
breaks. Quoted roots are protected too. Ordinary prose, including apostrophes
and balanced bracketed phrases, may precede a wrapper.

Both ports use the same repair padding around the wrapper and body, including
BOM and Unicode separators. Language tags contain ASCII letters. A wrapper
without a closing fence retains its remaining body for later repairs.

### Closing delimiters

`fix_closers` balances braces and brackets while preserving both quote styles
and comment contents. Missing inner closers are inserted before an existing
outer closer: `{"a":[1}` becomes `{"a":[1]}`. `fix_truncated` uses this balancing
step when it encounters that mismatch, then handles incomplete keys or values.

Closing delimiters at EOF are placed before trailing comments. Unmatched
closing delimiters and unfinished quoted strings are left to other strategies;
balancing does not append syntax inside a string value.

### Tokenizer artifacts

`fix_encoding` preserves characters such as `Ġ`, `Ċ`, `ĉ`, and `č` when they
appear only inside quoted strings or comments. An unquoted marker signals an
encoded document; the strategy then decodes those markers throughout the text,
including quoted content. Both quote styles and escaped quotes are recognized.
This preserves literal Unicode while repairing unrelated syntax such as bare
keys or missing closing delimiters.

### Inner quotes

`fix_inner_quotes` escapes unescaped double quotes inside object values, array
items, and root strings. Existing escape pairs, quoted keys, single-quoted
strings, and comments retain their literal text.

A quote ends a value when the next character after repair padding and comments
is a comma, closing brace, closing bracket, colon, or EOF. Other quotes inside
that value are escaped. Quotes immediately before those delimiters remain
boundaries because their intended role is ambiguous.

### Unquoted object keys

`fix_keys` quotes labels in object member positions. Accepted labels follow
`[A-Za-z_$][A-Za-z0-9_.$-]*`, so dots and hyphens stay part of the property name.
Both quote styles and comment contents retain their literal text. Comments may
appear before a key or between its label and colon.

Both ports use the same ASCII and Unicode repair padding, including control
separators and a byte order mark. Padding between a label and colon is removed
when it contains no comments. Comments and their surrounding padding are copied
unchanged; other input spacing is retained.

### Raw control characters

`fix_newlines` escapes raw U+0000–U+001F inside quoted strings and keys.
Backspace, tab, line feed, form feed, and carriage return use `\b`, `\t`, `\n`,
`\f`, and `\r`; other C0 characters use `\u00XX` escapes. Both quote styles
are recognized, and existing escape pairs retain their spelling.

An invalid backslash/control pair retains both literal characters by escaping
the backslash and the control. Structural whitespace, comments, and characters
above U+001F are preserved.

### Conversion from single quotes

`fix_quotes` converts strings and keys delimited by single quotes into JSON
strings. It removes an escape used for an apostrophe, preserves other escape
pairs, and escapes a double quote only when it was unescaped in the input.
Escaped backslashes are consumed as pairs so a path ending in a backslash does
not swallow the closing delimiter.

An unfinished string is closed at the end of input. A final unpaired backslash
is retained as a literal backslash by escaping it before adding the quote.
Existing double-quoted strings and comments are copied unchanged. Malformed
Unicode and byte escapes remain available to the later escape-repair strategy.

### Ellipsis placeholders and comments

`fix_ellipsis` recognizes standalone, unquoted `...` tokens. A root placeholder
or an object property value becomes `null`. An array element or object member
placeholder is removed with one adjacent separator, retaining the surrounding
real values. `[...]` and `{...}` become empty containers. Quoted strings such as
`"..."` and `"...more"` retain their contents. Longer dot runs and tokens such
as `...name` or `1...2` are left unchanged.

Comment removal recognizes both quote styles and escaped boundaries. It inserts
a space when deleting a block comment would join bare tokens, so `1/* note */2`
does not become `12`. Line comments end at LF, CR, CRLF, or Unicode line/paragraph
separators; the Unicode separators become newlines. An unfinished comment runs
to the end of input. Extraction ignores braces and brackets in comments, and
ellipsis repair uses the same comment handling before scanning placeholders.

### Trailing commas

`fix_commas` removes a trailing comma and the padding between it and a closing
brace or bracket. It preserves commas, brackets, and whitespace inside quoted
strings, including escaped quotes and backslashes. Both single- and double-quoted
strings are recognized so later quote conversion retains their contents.

The ports accept the same padding after a trailing comma: ASCII and Unicode
whitespace, control separators, and a byte order mark. Quoted occurrences remain
unchanged. Ellipsis cleanup uses the same comma handling. Extraction also respects
both quote styles when looking for a container's closing brace or bracket.

### Truncated JSON

`fix_truncated` tracks object keys, values, arrays, and quoted strings while
scanning the document. It closes missing containers and strings, retains array
items and whitespace inside unfinished string values, and preserves a final
literal backslash by escaping it before closing the string. Root strings and
leading JSON whitespace are supported.

A property with a colon but no value is retained with `null`. An unfinished
key without a colon is discarded, including its preceding comma. Empty trailing
separators are removed. Complete JSON is returned unchanged, including its
outer whitespace. Partial numbers and keywords are not completed by guessing
their missing characters.

The extractor preserves quoted roots so brackets in string content cannot be
mistaken for a separate object or array. Unbalanced object/array fragments
following surrounding prose remain available to later repair strategies.

### Unicode Escape Repairs

`fix_unicode` preserves valid JSON escapes and repairs malformed escapes inside
double-quoted keys and values. Incomplete `\u` escapes are padded with leading
zeros: `\uE9` becomes `\u00E9`. Byte escapes such as `\x41` become their character
values. Quotes, backslashes, and control bytes remain JSON-escaped; `\x00`
becomes `\u0000`.

A `\u` marker with no initial hex digit is removed along with up to four
following non-hex code points, stopping at whitespace, a quote, or another
escape. The legacy `\0` marker is removed and subsequent characters remain.
Incomplete `\x` escapes are left unchanged. These rules match in both ports.

## `parse()`

Use this when invalid output should fail immediately.

```python
from outputguard import parse

payload = parse('{"name": "Ada", "score": 1}', schema)
```

`parse()` validates, attempts repair if needed, returns parsed Python data, or
raises `ParseError` / `SchemaValidationError`.

An accepted null returns `None`. A null rejected by the schema, including one
recovered by repair, raises `SchemaValidationError`. `ParseError` means the
document could not be parsed after repair.

## `retry_prompt()`

Use this after a validation failure when you own the retry loop.

```python
from outputguard import retry_prompt, validate

result = validate(raw_text, schema)
if not result.valid:
    prompt = retry_prompt(raw_text, schema, result.errors)
```

The returned string explains what failed and asks the model to try again with
schema-compatible structured output.

Schema summaries describe boolean roots, forbidden properties, array item
constraints, and positional item schemas. A `False` root has no satisfying
output; guarded generation still follows the configured retry budget and
returns an exhausted result or raises when requested.

Nested details include nullable containers and schemas with no declared type.
Object and array guidance applies only to types allowed by the schema; a union
allowing both can include both sets of constraints. Summaries visit the root
and at most two nested container levels. References are not expanded, and
Draft 7 reference siblings remain ignored.

Property names follow JavaScript's enumeration order in both ports: canonical
integer names from `"0"` through `"4294967294"` appear in numeric order, followed
by other names in insertion order. Leading-zero and negative names belong to
the latter group. The caller's schema and required-field list are not changed.

By default, the retry prompt includes the previous model output in an
`Original output:` section. Text up to 500 Unicode code points is included
unchanged; longer text keeps the first and last 250 points, separated by
`\n...\n`. Supplementary characters count as one point; combining and joined
emoji sequences can span multiple points. The full original text remains in
results and generation contexts.
Turn off this excerpt with:

```python
prompt = retry_prompt(
    raw_text,
    schema,
    result.errors,
    include_message_history=False,
)
```

Validation error messages remain in the prompt and can include offending values,
even when the original-output excerpt is omitted.

## `guarded_generate()`

Use this when you want OutputGuard to coordinate generation, validation, repair,
and retry in one call.

```python
from outputguard import guarded_generate


def generate(prompt: str, context) -> str:
    return call_model(prompt)


result = guarded_generate(
    prompt="Return a YAML object with name and score.",
    schema=schema,
    generate=generate,
    format="yaml",
    max_retries=2,
    include_message_history=False,
)

print(result.valid)
print(result.data)
print(result.attempts)
```

See [guarded-generation.md](guarded-generation.md) for result fields and retry
behavior.

## `guarded_generate_async()`

Use this with async model clients.

The async wrapper accepts synchronous providers and observers too. Retry limits,
formats, and callback callability are checked before invoking the provider.
See [configuration and retry limits](guarded-generation.md#configuration-and-retry-limits).

```python
from outputguard import guarded_generate_async


async def generate(prompt: str, context) -> str:
    return await call_model_async(prompt)


result = await guarded_generate_async(
    prompt="Return a JSON object with id and status.",
    schema=schema,
    generate=generate,
)
```

## Batch APIs

Use `validate_batch()` when you need validity and parsed data for many outputs.
Use `repair_batch()` when you need repaired text for many outputs without schema
validation.

```python
from outputguard import validate_batch, repair_batch

validation = validate_batch(["{'name': 'Ada', 'score': 1}"], schema, format="python-literal")
repairs = repair_batch(['{"name": "Ada",}'])
```

See [batch-processing.md](batch-processing.md) for result objects and CLI usage.

## Error Handling

Package-specific exceptions derive from `OutputGuardError`, including
`GuardedGenerationError`. Catch the common base to handle library failures,
or the specific subclass to inspect its structured payload. Provider and
observer failures retain their original types and values.

`StrategyError(message, strategy_name)` identifies a failure in a custom repair
strategy. Its `strategy_name` field retains the supplied name. When a strategy
raises it during repair, the pipeline records the message on that strategy's
report step, keeps the step's input text, and continues with later strategies.
The report attributes the step to the registered strategy name. An empty error
message is reported as `StrategyError`.

`SchemaEvaluationError` means recursive schema evaluation could not complete,
including a reference cycle that makes no progress or exhaustion of the
engine's available stack. It propagates from validation, strict parsing,
batches, and guarded generation. Its `data` field holds the parsed value,
`schema` is the supplied root, and `format` retains the selected spelling.
`error.__cause__` retains the underlying evaluation failure.

Ordinary schema mismatches still produce validation results, and malformed
text still produces a parse failure. Productive references that descend into
nested data continue to work. Parser and evaluation limits remain specific to
the runtime; this error does not impose a shared numeric nesting limit.
Generation propagates it immediately, before observer notification or another
provider call, including when repair is disabled. Other configuration,
reference-lookup, and cancellation exceptions keep their original types.


OutputGuard raises package-specific exceptions for strict parse paths. The most
common 2.0 guarded-generation error is `GuardedGenerationError`, raised when
guarded generation cannot produce valid output within the retry budget and
`throw_on_failure=True`.

Use non-throwing result objects when you need to record failed attempts instead
of interrupting a pipeline.
