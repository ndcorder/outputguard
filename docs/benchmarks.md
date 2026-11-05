# Benchmarks and parity checks

The Python and JavaScript repositories carry identical `benchmarks/cases.json`
fixtures. Each test suite checks the corpus against explicit expected results.
The cases cover clean output, syntax repairs, repaired schema failures, nulls,
nested errors, prototype-named keys and schema constraints, references, batch
summaries, boolean schemas, dependencies, reused and prototype-named relative
IDs, ignored metadata, references into literal annotations, resource-discovery
failures, retry prompts, and the supported formats. Parser error wording and
JSON Schema validator messages differ between runtimes; comparisons use validity, parsed
data, repaired text, strategies, error paths and values, and parse-failure status.
Batch comparisons use every summary field, including format and strategy counts.
Retry prompt comparisons use explicit expected prompts. Unicode-history cases
check exact errors, format labels, included/omitted history, 499/500/501-point
boundaries, emoji cut points, combining characters, CRLF, and lone surrogates.
ASCII and emoji workloads also scale to 10,000 points. Supplied error messages
are identical across ports; native validator message wording is not compared.
Schema-summary cases compare complete prompts for numeric property order,
nullable/typeless containers, mixed object/array schemas, applicable keywords,
reference siblings, and depth bounds. Required-field workloads scale from 1 to
1,000 properties, with every name required; nested schemas scale to 100 levels
while the summary visits only the root and two nested containers. Real-process
CLI contracts compare the complete schema-summary section as well as history.
Cases with `operation: "expect_unresolvable"` require each validator's native
missing-reference exception and normalize only its category. Other exceptions
and unexpected successful lookups fail the check.
Cases with `operation: "validate"` check parsing and validation without repairs.
Cases with `operation: "strategy_apply"` time a single named strategy and compare
its exact output text. These cover atom boundaries and scaling from 30 to 3,000
bare values for `fix_values` and `fix_booleans`.
Python-string workloads (`python_string_{escapes,raw,triple,adjacent}_{1,100,1000}`)
check exact decoded text while scaling escape sequences, raw contents,
multiline strings, and adjacent literal tokens. Fenced Python strings also
check schema failures after removing the fence.
Python-number workloads (`python_number_{decimal,binary,octal,hexadecimal,float,unary}_{1,100,1000}`)
scale arrays of real-number literals. Invalid-underscore cases put a malformed
number after a growing valid prefix. Fenced-number cases retain schema errors,
and an overflow batch checks classification without transporting infinity as
JSON data. Long-fraction and zero-integer cases scale individual tokens from
30 to 3,000 zero digits, with invalid trailing underscores or a nonzero digit
after the integer's leading zeros. Fraction unit checks also use 30,000 digits.
YAML workloads scale scalar sequences, mappings, explicit core tags, Unicode
literal blocks, and scalar/container aliases from 1 to 1,000 entries. Late
duplicate-key and unsupported-tag cases check failure scaling. Boundary cases
exercise the exact alias-amplification rule; other cases cover dates, regexes,
empty/prototype keys, fences, auto detection, and batch failure categories.
TOML workloads check string/date schema assertions, exact timestamp fractions
and offsets, omitted seconds, TOML 1.1 escapes and inline tables, unsafe property
names, and fenced repairs. Scalar and timestamp mappings scale to 1,000 entries.
Configuration workloads check aliases, casing, BOM/Unicode padding from 1 to
1,000 repetitions, and batch sizes 0, 1, 100, and 1,000. Batches inherit a guard's
format or override it while retaining the selected spelling in summary counts.
Mixed-batch aggregation workloads combine valid documents, schema failures,
fenced repairs, and parse failures at sizes 0, 1, 100, and 1,000. Timings cover
the complete public batch call, including result collection and summary counts.
Strategy-selection workloads time registry filtering and guard construction with
all, empty, and restricted selections. Duplicate lists scale from 1 to 1,000
names; duplicates run once in registry order. Configured repair workloads include
guard construction and check clean/broken input with full, restricted, or disabled
repairs. These fixtures also assert the complete execution order in both ports.
Schema-free repair workloads scale invalid arrays and Unicode strings from 1 to
1,000 entries, with and without detailed reports. They check original-text
rollback, retained candidates, tried strategies, and confidence. Report timings
include deriving the candidate, strategy/error lists, and confidence; plain repair
timings stop at the repair result. Both include guard construction. Separate shared
repair contracts inject throwing, non-string, and async strategies and check
all fallback passes, error records, and exact report metadata. Each fixture runs
through both the guard and top-level helper with reports enabled and disabled.
Typed `StrategyError` failures also check recovery and rollback across formats,
empty and Unicode diagnostics, and attribution to the registered strategy name.
Public-helper workloads separately time clean input, failed repair, and Unicode
strings with 1, 100, and 1,000 repetitions. Their timings include the public
repair call and report construction; report normalization runs before timing.
Diff workloads time report patches, individual strategy patches, and combined
step details on sparse, repeated, and disjoint text from 1 to 10,000 rows per
generated block. Repeated disjoint blocks check that duplicate new lines are
not treated as matches. Workloads with a shared middle block change both ends
of the text, checking overhead when alignment is still required.
Imbalanced report workloads replace a single line with growing blocks. Inputs
and expected patches are prepared before timing; both report construction and
formatting are timed. Exact shared contracts also check LF/CRLF, unterminated
lines, context grouping, Unicode separators, escaped labels, and bounded-search
fallbacks. A separate patch reader applies and reverses every patch, small
sequence tests verify minimal edit counts for all 14,641 pairs of sequences
with up to four rows drawn from three symbols, and Git independently checks UTF-8
fixtures. Repair contracts compare complete diff/detail strings across ports.
Input workloads check explicit TypeErrors for unsupported text and late invalid
batch items. Valid batches scale from zero to 1,000 documents. Shared input
contracts compare native strings, empty-document behavior, public/guard entry
points, batch snapshots, and provider/observer call counts. Both test suites
expand the same fixture specification and the cross-port gate checks the expansions.
Schema-root contracts also check objects/booleans, invalid roots with clean or
malformed document text, empty batches, and zero provider/observer calls.
Schema rejection workloads use null, number, string, and array roots; batch
sizes scale from zero to 1,000 items and must fail before copying inputs.
Schema mutation workflows edit a reused root, invalidate it explicitly, and
compare validity, parsed data, error paths, and missing-reference recovery
through validation, repair, parsing, and both batch validation modes.
Invalidation-only workloads scale from 1 to 1,000 properties and do not compile.
Validation-after-invalidation workloads scale to 100 fields and include fresh
compilation on every timed call while retaining the root object identity. They
are marked `schema_mode: "fresh"`; invalidation-only calls use `"none"`.

Direct evaluation-cost controls time reference-free booleans, empty/type
schemas, simple references, and productive reference chains of 1, 5, and 20
levels. These keep parsed output, error paths, and error values identical while
measuring the cost of per-call recursion isolation.

Evaluation-failure contracts exercise recursive references through raw/public
validation, repair, strict parsing, batches, and guarded generation. They compare
the error type, message, parsed data, root identity, format, cause, and callback
counts. Benchmarks time repeated failures on root, definition, and negated
reference cycles. CLI contracts require an operational exit and diagnostic.

Guarded-generation outcome contracts run synchronous and asynchronous callbacks
with throwing enabled and disabled. They compare complete attempt outcomes,
parsed data, final errors, repair history, strategy order, and callback counts.
They also check the identity of previous results and observed attempts,
message-history flags, error messages, and catchability through the common
error base.

Unicode repair contracts cover all 256 byte escapes in keys and values,
incomplete and malformed Unicode escapes, escaped-backslash boundaries,
whitespace, literal escape-looking text, and prototype-named keys. They compare
exact strategy output, decoded values, report rollback/candidates, and default
schema-validation repairs. Scaling workloads time byte conversion, preserved
escapes, unknown byte escapes, and escaped quote/backslash/control-byte repair
from 1 to 1,000 repetitions.

Truncation contracts compare exact strategy candidates, accepted or rolled-back
report text, parsed values, and public validation metadata. They distinguish
unfinished keys from array and object values, check escaped string boundaries,
preserve string whitespace and backslashes, and retain missing values as null.
Scaling workloads cover complete documents, numeric arrays, string lengths,
nested containers, trailing separators, missing values, and dangling keys.

String repair contracts check exact candidates, report rollback, and public
validation results for delimiter-looking string content, both quote styles,
escaped quote/backslash boundaries, and shared trailing-comma padding. They also
check extraction and ellipsis cleanup through the default repair sequence.
Comma workloads scale clean arrays, trailing separators, nested objects, quoted
literal patterns, unfinished strings, and padding from 1 to 1,000 repetitions.

Ellipsis contracts cover dense and mixed placeholders, quoted literal text,
object property values and omitted members, root nulls, comments, and unsupported
partial tokens. Comment contracts check both quote styles, token boundaries,
line terminators, unfinished comments, and extraction around commented braces.
Scaling workloads compare clean arrays and strings, nested empty containers,
property values, dense placeholders, block/line comments, long comments,
quoted markers, and invalid primitive joins from 1 to 1,000 repetitions.

Quote-conversion contracts compare decoded values and exact output for generated
combinations of apostrophes, quotes, backslashes, control escapes, Unicode,
prototype-named keys, unfinished strings, and comments. They check raw candidates,
report rollback, and public repairs, including schema failures after conversion.
Scaling workloads cover clean JSON, apostrophes in existing JSON strings,
arrays of strings using single quotes, escaped apostrophes/quotes, long bodies,
and paths ending in backslashes from 1 to 1,000 repetitions.

Control-character contracts cover every raw C0 character in root strings,
values, array items, and keys; odd/even backslash runs; preserved escape pairs;
comments; both quote styles; unfinished strings; and schema failures. Negative
cases retain controls outside strings and valid Unicode characters. Workloads
scale clean/pretty JSON, existing escapes, raw newlines, the complete C0 range,
and odd/even backslash boundaries from 1 to 1,000 repetitions.

Key-repair contracts enumerate accepted ASCII labels, nested object/array
positions, quoted literal patterns, prototype-named properties, comments around
keys, and shared padding. Negative cases retain unsupported key spellings and
array/root contexts. Workloads scale quoted and bare mappings, nesting, long
labels, protected strings, comments, and padding from 1 to 1,000 entries or
repetitions.

Inner-quote contracts check exact decoded values in object, array, nested, and
root positions; valid escapes; quoted keys; single-quoted literals; shared
padding; comments; delimiter boundaries; and schema failures. Scaling workloads
compare clean objects, repeated object/array repairs, dense root quotes, long
values, existing escapes, comments, and quote-free arrays from 1 to 1,000
entries or repetitions. The scanner copies unchanged spans and joins once.

Encoding contracts preserve literal marker characters while repairing bare
keys, single quotes, truncation, and comments. Separate framing-marker cases
check whole-document decoding. Workloads scale clean input, quoted literals,
comments, and early/late framing signals from 1 to 1,000 repetitions.

Closer contracts enumerate missing-delimiter combinations in nested arrays and
objects, exact literal preservation, comments, unfinished strings, unmatched
closers, and public truncation recovery. Workloads scale clean/quoted values,
comments, nested objects, missing internal closers, and unsupported mismatch
runs from 1 to 1,000 entries or levels. Truncation attempts mismatch balancing
once per scan, including when recovery cannot produce a candidate.

Comparisons preserve JSON types: booleans never equal numbers. Numbers compare
by value, so `1` equals `1.0` and `0` equals `-0`. Object property order is
ignored; array order is preserved. Non-JSON values such as non-finite numbers
fail the check. Mismatches identify the first differing path, including nested
error values and batch summaries. These checks run before the timed section.

Run from the Python repository after installing its development dependencies:

```bash
uv run python -m benchmarks.run
uv run python -m benchmarks.run --iterations 1000 --samples 7
uv run python -m benchmarks.run --clock cpu --iterations 2000 --samples 7
uv run python -m benchmarks.run --results
uv run python -m benchmarks.run --case clean_json --case literal_ref_examples_pattern_valid --iterations 2000 --samples 7
```

Run from the JavaScript repository after installing dependencies and building:

```bash
pnpm build
node benchmarks/run.mjs
node benchmarks/run.mjs --iterations 1000 --samples 7
node benchmarks/run.mjs --clock cpu --iterations 2000 --samples 7
node benchmarks/run.mjs --results
node benchmarks/run.mjs --case clean_json --case literal_ref_examples_pattern_valid --iterations 2000 --samples 7
```

Use `--case NAME` to profile specific workloads; repeat it to select several.
Names match exactly, repeated names run once, and results retain fixture order.
Unknown names fail before results or timings are produced. Selection also
applies to `--results`. Omitting `--case` runs the full corpus, and the
cross-checkout parity command below always checks the full corpus.

`--clock wall` (the default) measures elapsed time. `--clock cpu` measures
user plus system CPU time for the benchmark process, including runtime threads.
It excludes time the process is not scheduled or is sleeping. Concurrent work
inside the process, such as JIT/GC threads, is included; CPU time can exceed
elapsed time when threads work on multiple cores. Use wall time to measure
latency. Processor frequency and other host conditions still affect CPU time.

Python uses `time.process_time_ns()`; Node gets integer microsecond readings
from `process.cpuUsage()`. Both report microseconds per operation; actual clock
resolution depends on the OS and runtime. Readings
are taken once per batch of iterations, so increasing `--iterations` amortizes
clock overhead and reduces quantization in short CPU-time workloads. CPU and
wall times must not be compared as the same metric.

Every timing report includes `clock` and an `environment` object with `start`
and `end` observations. Each observation contains `logical_cpus` and
`load_average` (1-, 5-, and 15-minute system load averages). Unavailable values
are `null`; Windows load averages are reported as unknown instead of zero.
The CPU count is what the OS reports, and may differ from a process's CPU quota
or affinity. Observations are collected outside the timed loops and do not
automatically mark a run reliable or unreliable.

`--results` checks correctness only and does not read clocks or collect host
observations. Iteration and sample counts must be positive, base-10 safe
integers in both runners. Invalid arguments exit `2` before producing JSON.
Use `--help` for the available options.

Keep host activity comparable when interpreting timing reports. Backups,
indexing, thermal throttling, and other workloads can move unchanged control
cases as well as changed code. Matching runtime/platform fields do not establish
stable CPU conditions. Treat a run with broad control-case spikes as
inconclusive and repeat it under comparable load. Interleaving before/after
samples in one process can help with targeted algorithm comparisons.

The runners check correctness before timing, warm up each case 50 times, and
report median and minimum microseconds per call across samples, rounded half up
to three decimal places in both ports. JSON output
includes runtime, platform, clock, host observations, iteration counts, and
sample counts. Timings cover
the operation named in each fixture: validation, validation with repair, a batch
helper, a retry prompt, or a single repair strategy. API timings include parsing,
schema validation, and any repairs. Batch
timings cover the entire batch call. Startup, imports, and building the JavaScript
package are outside the timed section. There are no timing thresholds in the test suites.
The JavaScript runner reuses each schema object after its correctness and warmup
passes, so successful compilations are cached during timed calls. Expected
missing-resource cases repeatedly attempt compilation; failed compilation is
not cached, even when the schema object is reused.

Cases marked `fresh_schema: true` clone their schema before every call instead.
Those timings include cloning and, in JavaScript, compilation with an isolated
registry. Python uses a JSON round trip to clone fixtures; JavaScript uses
`structuredClone`. Compare fresh and reused cases within the same runtime to
assess the cost of a schema object's lifetime.
Each measurement includes `schema_mode` (`fresh`, `reused`, or `none`) so
reports can separate these workloads.

Save two timing reports, then compare them using either checkout:

```bash
uv run python -m benchmarks.compare before.json after.json
node benchmarks/compare.mjs before.json after.json
```

The JSON comparison matches exact case names, preserves the after report's
order, lists added and removed cases, and summarizes median ratios separately
for reused, fresh, and schema-free workloads. A ratio above `1` means slower;
positive percentage changes mean increased latency. Changes beyond the default
5% threshold are labeled `regressed` or `improved`; exact threshold boundaries
are unchanged. Classification uses unrounded ratios. Displayed ratios use six
decimal places and percentages use three.

Use `--threshold 10` to choose another percentage, or `--fail-on-regression` to
return exit status `1` when any comparable case regresses. The comparison JSON
is still produced when this gate fails. Invalid arguments or reports exit `2`
without partial JSON. The normal reporting command exits `0` even if it finds
regressions. Use `--fail-on-incomparable` to exit `1` when matching cases have
changed clocks or schema modes; this gate also preserves the comparison JSON.
It can be combined with `--fail-on-regression`. Neither gate fails merely
because cases were added/removed or timings were zero. Timing gates are opt-in
and are not part of the test suites.

Both reports must contain runtime/platform information, iteration/sample/warmup
counts, unique names, valid schema modes, and finite nonnegative median/minimum
timings. The comparison identifies changed measurement conditions; use matching
conditions when drawing performance conclusions. Reports without a `clock`
field are older wall-time reports; an explicit unknown clock is rejected. A
changed clock or schema mode marks matching cases `incomparable`; a zero median
on either side marks them `unmeasurable` when the clock and mode agree.
These rows have no ratio or percentage and do not enter median summaries or
the regression gate. Clock changes add `before_clock` and `after_clock` to
incomparable rows. Added and removed cases also have no timing comparison.
The comparison preserves normalized environment observations separately from
measurement conditions. Missing observations remain `null`; changes in load
are context for interpretation and do not change regression classification.

With both checkouts available, run this from the Python repository:

```bash
uv run python -m benchmarks.check_parity --js-repo ../outputguard-js
```

This command requires Node on `PATH` and a current JavaScript build. It checks
that the fixture copies are identical, validates expectations in both runtimes,
and compares their normalized output. Individual repository tests work without
the sibling checkout.

The command also checks identical report-comparison and numeric fixtures and
compares both implementations against their explicit expectations. It also
checks identical schema-format fixtures and bundled format patterns, then
verifies both runtimes against the expected format decisions.
The shared `python_strings.json` fixtures check exact decoded values and parse
failure categories at the root, in an object property, and in a list. Each
port's tests additionally check false schemas, repair short-circuiting, aliases,
guards, batches, and generation feedback.
The `python_numbers.json` fixtures check real-number syntax and values in the
same locations, including base prefixes, underscores, unary grouping, malformed
tokens, overflow, and underflow. Unit checks distinguish signed zeros and retain
each runtime's native numeric representation. Cross-port JSON equality compares
zero by value; overflow fixtures use batch summaries instead of non-finite JSON.
The `yaml_cases.json` fixtures check core scalar rules, decoded keys, tags,
directives, Unicode, block styles, aliases, and failures in the same locations.
Non-finite values use batch summaries in JSON transport and direct value checks
in each test suite. The gate also checks Python's embedded YAML engine against
its manifest, JavaScript source hashes, installed YAML version, core patterns,
and dependency license.
The `toml_cases.json` fixtures check date/time text, calendar/clock failures,
1.1 syntax, number types, duplicate keys, table scopes, Unicode, and line endings.
The gate verifies the private JavaScript parser and embedded Python engine
against their manifest, sources, dependency version, and BSD notice. Integers
outside JavaScript's safe range have separate native tests; they are excluded
from shared JSON-data comparisons. Non-finite values use batch summaries.
The `configuration_cases.json` fixtures check supported spellings, every
ECMAScript trimming code point, non-trimming controls, invalid types, attempt
limits, callback types, and provider results. The gate expands these into
contracts checked against explicit expected outcomes in Python's sync and async
wrappers and JavaScript. It compares configuration-error categories, selected
format spelling, results, batch counts, and provider/observer invocation counts.
Unexpected exceptions fail the check rather than being treated as ordinary
document failures.

After changing the YAML profile, bridge, patterns, build script, or YAML
dependency, rebuild the Python artifact from the JavaScript checkout:

```bash
pnpm yaml:engine
pnpm yaml:engine --check
node benchmarks/build_yaml_engine.mjs --python-repo ../outputguard
```

The builder uses the installed `tsup` toolchain, stages output in a temporary
directory, and writes the bundle, source manifest, core patterns, and ISC notice
into the Python package. `--check` rebuilds and compares without writing those
files. Python installations run the checked-in bundle using QuickJS-NG and need
no Node executable. Numeric graph records retain source text so Python can
construct its own numbers; reference IDs preserve alias identity. Runtime
contexts are isolated by thread and reset after a fork.

Rebuild the TOML artifacts after changing their sources or dependency:

```bash
pnpm toml:engine
pnpm toml:engine --check
node benchmarks/build_toml_engine.mjs --python-repo ../outputguard
```

This builder substitutes Outputguard's date validator in a private copy of
smol-toml. It writes `src/vendor/tomlParser.js` in JavaScript and the engine,
manifest, and BSD notice in Python. It does not patch installed modules or
global Date/Temporal behavior. `--check` compares both generated parsers without
writing them. Python decodes integer/float graph records into native numeric
types; neither date precision nor integer digits pass through JSON numbers.

For reproducible generated schema/data pairs, run from the Python repository:

```bash
uv run python -m benchmarks.check_schema_fuzz
uv run python -m benchmarks.check_schema_fuzz --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --diagnostics --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --resources --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --fragments --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --scopes --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --evaluation --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --numeric --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --formats --cases 2400 --seed 6293
uv run python -m benchmarks.check_schema_fuzz --regex --cases 2400 --seed 6293
uv run python -m benchmarks.check_parsing_fuzz --cases 2400 --seed 6293
uv run python -m benchmarks.check_parsing_fuzz --python-strings --cases 2400 --seed 6293
uv run python -m benchmarks.check_parsing_fuzz --python-numbers --cases 4800 --seed 6293
uv run python -m benchmarks.check_parsing_fuzz --yaml --cases 4800 --seed 6293
uv run python -m benchmarks.check_parsing_fuzz --toml --cases 4800 --seed 6293
```

This command compares validation decisions for schemas composed from property
constraints, arrays, schema combinators, patterns, and escaped keys. Boolean
property constraints, dependencies, reference siblings, repeated root IDs, and
embedded resource IDs are included alongside typed schemas. Resource IDs and
reference targets include prototype names such as `constructor` and `__proto__`,
as well as local, parent-relative, and rooted resource paths.
Ignored `$async` annotations appear in nested schemas and behind references.
Generated references also select schemas inside `const`, `enum`, and `default`
values. The JavaScript runner requires a boolean validity result for every case.
The command prints the full first mismatch or failing case and seed for
reproduction. It requires both checkouts
and a current JavaScript build. Generated comparisons check agreement between
the ports; the shared corpus separately checks explicit expected results and
diagnostics.

`benchmarks.check_parsing_fuzz` constructs known data and malformed JSON together,
without using either repair implementation to calculate expected results. It
checks parsing with repairs disabled, repaired text and data, strategy order,
parse-versus-schema failure classification, and root diagnostics. Cases mix
nonstandard constants and Python booleans with escaped and prototype-named
keys, literal token spellings, trailing backslashes, nested arrays and objects,
`const`/`enum`/`uniqueItems`, and references. Both ports must satisfy the explicit
expectations before their normalized results are compared. Failures print the
case and seed for reproduction.

With `--python-strings`, that checker composes explicit string fixtures and
their known values using mixed prefixes, quote forms, escapes, comments,
line joining, parentheses, nested containers, and schema references. Both
ports must return the constructed data or the expected parse/schema failure.
Malformed strings run with repairs disabled. Named Unicode escapes and other
Python-only literal types are outside this portable corpus. Separately escaped
surrogates are checked individually, since adjacent high/low surrogates can
coalesce into one UTF-16 pair when JavaScript serializes them.

With `--python-numbers`, the checker constructs integer bases, float parts,
exponents, underscores, unary signs, grouped operands, and known numeric values.
It combines them with containers and schema references and checks malformed
fixtures with repairs disabled. Generated arithmetic stays within exactly
representable integer intermediates before division, so expected floats have
one rounding step. YAML, string, and number modes are mutually exclusive;
omitting all three checks JSON repairs. Large-integer precision differences remain documented
in the format guide.

With `--yaml`, the checker constructs known data together with block/flow
containers, core scalar/number spellings, aliases, keys, and schema references.
Malformed fixtures run with repairs disabled; valid inputs also test repair
short-circuiting and duplicate alias values under `uniqueItems`. Auto-detection
cases use a document marker to select YAML unambiguously. Both runtimes must
satisfy those expectations before their normalized output is compared.

With `--diagnostics`, the generator composes false constraints while tracking
their expected instance paths and values. It checks each runtime against those
expectations. Cases include repeated array failures, escaped and prototype-named
properties, patterns, additional-property schemas, embedded resources, and
references through literal annotations. The seed and full first failing case
are printed for reproduction.

With `--resources`, generated cases check explicit expected validity or a native
missing-reference exception. They cover declared Draft 7 schema locations,
ignored IDs in annotations and later-draft keywords, legacy fragment anchors,
reference siblings, duplicate ignored IDs, literal comparisons, and pointer
scopes under unregistered resources. Mixed dependency maps include property
lists, boolean schemas, and object schemas in both orders. This mode checks each
port independently against the generated expectations before comparing them.

With `--fragments`, the generator checks URI-encoded pointer separators, valid
plain-name anchors, escaped tokens, percent-named schema locations, references
inside literal values, mixed dependency resources, recursion, and missing
targets. Array-index checks include canonical indexes, leading zeros, signs,
whitespace, non-ASCII digits, and numeric-looking literal object keys, including
nested arrays and embedded resources. Target-type checks reject scalar and array
targets and traversal through scalars or booleans, while retaining boolean-schema
validity and error locations. It independently tracks expected validity, error
paths, and error values for each port. Python first uses native resolution and retries affected
lookups with compatibility views, so those timings include the failed native
attempt and preparation. JavaScript's reused-schema timings use its compiled
validator cache as described above.

With `--scopes`, generated cases distinguish actual schemas, schema maps, and
pointer-selected data. They cover dependency triggers named `$id`, subschemas
with keyword-like names, nested IDs, recursive references, annotation traversal
after `items` and `dependencies`, whole-map schema targets, closed objects, and
shared map literals. Expected validity, error paths, values, and missing-resource
outcomes are tracked independently, including collisions with existing resource
IDs and repeated lookups after a map is selected as a schema. Python establishes
pointer roles lazily during the initial lookup; fragment fallbacks can still
add a second validation pass as described above.

With `--evaluation`, generated cases independently check validity and missing
resources under `if`, `contains`, `not`, and `oneOf`. They cover colliding IDs,
explicit Draft 7 declarations, annotation targets, embedded resources, recursion,
and ignored IDs beside `$ref`. This mode compares boolean validity because the
native validators can expose different diagnostic detail counts for failed
applicators.

With `--numeric`, the generator constructs decimal multiples from integer
coefficients and scales, and nonmultiples by adding one unit at an extra decimal
place. For whole-number values, a rational oracle checks the exact parsed
integers, including values beyond JavaScript's safe integer range. It also
samples explicit regression cases for roundoff, nearby invalid
values, signs, zero, subnormals, extreme exponents, and integer boundaries.
Cases cover direct constraints, arrays, properties, resources, annotation
targets, and boolean applicators. Expected validity is independent of either
validator. Non-applicator cases within JavaScript's safe integer magnitude also
check instance paths and values; other cases compare validity.

When adding a case, update both fixture copies and run both suites. Compare
performance changes on the same machine, runtime, dependencies, and benchmark
settings. These small fixtures exercise common paths; they do not establish
performance for large or adversarial documents.

With `--formats`, the generator composes schema-format checks around explicit
format examples, generated calendar dates, emails, IPv4 addresses, and escaped
JSON Pointers. Nested objects, arrays, prototype-named keys, references, and
annotation targets must preserve validity, instance paths, and rejected values.
Unsafe integers check validity only because JavaScript's JSON serialization can
print a rounded decimal spelling; the API corpus separately checks their
parse/schema classification through batch summaries. Regex format decisions now use ECMAScript syntax in both ports.

With `--regex`, expected matches come from explicit fixtures and constructed
named-capture/backreference strings. The generator checks whole-string anchors,
Unicode classes, lookbehind, surrogate keys, property patterns, closed objects,
regex-format decisions, nested arrays and objects, and references through
annotations. Both ports must match the expected decisions, paths, and values.
`ecma_scaling_*` cases measure closed objects with 1, 100, and 1,000 properties
using either ordinary character classes or named captures.

Python's compiled ECMAScript patterns are cached per thread by source and flags,
including across fresh schema objects. These caches hold patterns, not instance
text. The engine and its cache are created lazily; warmup excludes their initial
creation from timings. The cache is bounded to 128 pattern/flag pairs.

## CLI process contracts and benchmarks

With both checkouts installed and JavaScript built, run from Python:

```bash
uv run python -m benchmarks.check_cli_parity
uv run python -m benchmarks.check_cli_parity --node /path/to/node
uv run python -m benchmarks.check_cli_parity --benchmark-dir /tmp/cli-timings --samples 7
```

Both repositories carry identical `cli_cases.json` contracts. Unit tests exercise
the local CLI; the cross-port command starts real Python and Node processes in
isolated directories. It checks expected exit codes, separate stdout/stderr,
output files, flag aliases and clusters, `--`, encodings, CRLF/BOM preservation,
transport/schema errors, quiet mode, repairs, and large Unicode pipes. JSON
reports must be standard JSON. Normalization maps metadata field names and
omits engine-specific diagnostics while leaving model data intact. Python also
checks the minimum supported Click version. Separate tests split UTF-8 input
across slow writes and close an output pipe early.

The optional benchmark writes `cli-python.json` and `cli-js.json`, compatible with
the existing comparison tool. Every sample starts a new process. Reported wall
time includes startup, imports, input/schema reads, parsing, validation/repair,
output, and shutdown. Preparing fixture files and checking results are outside
the timer. Each sample runs one invocation; there are no warmups. Filesystem
caches can still be warm. The benchmark samples run serially after the parity
gate, independently of its `--workers` setting. Parent process CPU time would
exclude the CLI's work, so this benchmark reports wall time only.
