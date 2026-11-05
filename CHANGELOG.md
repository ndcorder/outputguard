# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Restrict source archives to distributable project files. Exclude local agent
  instructions and environment files while retaining runtime resources, tests,
  benchmark fixtures, docs, examples, and build metadata.
- Preserve fenced code inside quoted data and comments when stripping Markdown
  wrappers. Recognize wrappers through ordinary prose, align repair padding,
  and add shared literal-preservation contracts and fence scaling workloads.
- Balance missing inner delimiters before existing outer closers, and reuse
  that recovery in truncation repair. Preserve both quote styles and comments,
  place EOF closers before trailing comments, and retain unfinished strings
  and unmatched closers. Add shared structural contracts and scaling workloads.
- Preserve literal Unicode during encoding repair when marker characters occur
  only in quoted strings or comments. Require an unquoted marker before
  decoding the document, retain whole-document artifact repair, and add shared
  data-preservation contracts and scaling benchmarks.
- Repair inner double quotes in array items and root strings as well as object
  values. Preserve comments, quoted keys, single-quoted literals, and existing
  escape pairs; align repair padding across ports. Replace repeated prefix
  joins with a scan over quoted spans and add shared contracts and scaling
  benchmarks.
- Make unquoted-key repair aware of object member positions, both quote styles,
  and comments. Preserve literal text, quote keys adjacent to comments, and
  align ASCII/Unicode padding across ports. Add shared label/context contracts
  and key-repair scaling benchmarks.
- Extend `fix_newlines` to escape the entire raw C0 range inside quoted strings
  and keys. Preserve literal backslashes before raw controls, existing escape
  pairs, comments, structural whitespace, and other Unicode characters. Reuse
  quote/comment scanning and add shared range/boundary contracts and scaling
  benchmarks.
- Preserve escape pairs when converting single quotes to JSON. Repair escaped
  double quotes and paths ending in backslashes without changing their decoded
  values; retain final backslashes when closing unfinished strings. Reuse the
  shared quote/comment scanner and add generated preservation contracts and
  quote-conversion scaling benchmarks.
- Align ellipsis repair across ports: preserve quoted placeholders, remove bare
  array/member placeholders without joining real values, and retain missing
  property values as null. Replace repeated prefix joins with a linear scan.
- Share quote/comment scanning across extraction and repairs. Preserve single-
  quoted comment markers, retain primitive token boundaries, support additional
  line terminators, and consume unfinished comments consistently. Add shared
  correctness contracts and ellipsis/comment scaling benchmarks.
- Preserve literal comma/closer patterns inside quoted strings during trailing
  comma repair and ellipsis cleanup. Recognize both quote styles and escaped
  boundaries during extraction. Align trailing-comma whitespace handling across
  ports, and add shared string-preservation contracts and scaling benchmarks.
- Add the JavaScript port's missing public `StrategyError` counterpart. Share
  typed strategy-failure contracts for fallback recovery, rollback, empty and
  Unicode diagnostics, and report attribution across all supported formats.
- Replace truncation tail regexes with a shared structural scanning policy.
  Preserve array strings, unfinished string whitespace, and literal trailing
  backslashes; retain missing property values as null and drop only unfinished
  keys. Support quoted roots and leading JSON whitespace without changing
  complete JSON. Remove trailing separators in linear time.
- Preserve quoted roots during extraction and retain unbalanced container
  fragments for subsequent repair. Add shared truncation/report/validation
  contracts and scaling benchmarks.
- Encode quotes, backslashes, and control bytes correctly when repairing
  `\xHH` escapes. Preserve literal escape-looking text and valid JSON strings.
  Add shared byte/key/value contracts and Unicode strategy scaling benchmarks.
- Add shared generation outcome contracts for throwing/non-throwing calls,
  synchronous/asynchronous callbacks, retries, repaired schema failures, and
  all formats. Check callback error and cancellation propagation separately.
- Type repair results according to the report flag at module, guard, and raw
  entry points. Literal flags infer the corresponding result; dynamic booleans
  return a union. Add positive and negative static contracts checked in CI.
- Combine batch summary counts in one pass after collecting results, preserving
  final custom-guard metadata and exact strategy/format names. Add mixed-batch
  scaling benchmarks shared with the JavaScript port.
- Allocate reference-cycle tracking only when a reference is evaluated. Use
  token-based cleanup instead of a generator context manager on every call,
  while preserving thread, reentrant-call, cancellation, and error isolation.
  Add direct validation and productive-reference scaling benchmarks shared
  with the JavaScript port.
- Retry summaries include nullable and typeless containers and both object/array
  branches when applicable. Omit constraints for excluded types and preserve
  bounded traversal and ignored reference siblings. Match JavaScript's numeric
  property-name ordering without changing the caller's schema. Use set lookups
  for required names to avoid repeated linear scans on wide schemas.
- Reject invalid schema-root types with a consistent `TypeError`, before text
  parsing, batch input reads, or generation provider calls. Preserve boolean
  schemas, dictionary subclasses, and native keyword/reference handling. Add
  shared preflight contracts and scaling benchmarks for early rejection.
- Check a mutable guard's repair limit before validation-batch work, including
  empty batches. Validation without repair and schema-free repair ignore this
  unused limit.
- Document the shared retry-history rule: retain up to 500 Unicode code points,
  or the first and last 250 points separated by an ellipsis line. Add exact
  prompt contracts and generation integration checks for Unicode boundaries.
- Reject non-string document text and generation prompts with `TypeError`
  before parsing or provider calls. Reject objects that pretend to be strings
  without coercion. Preserve empty-string parsing and valid awaitable providers.
- Batch helpers now check and copy a sequence of strings before processing any
  item. Accept tuples; reject scalar/binary inputs and invalid items with an
  indexed diagnostic. Caller mutation cannot change the selected batch inputs.
- Skip diff alignment for empty sections, single-line replacements, and
  sections with no common lines. Preserve the exact patch while avoiding
  unnecessary token allocation and shortest-path searches.
- Emit matching, applicable unified patches for report and strategy diffs:
  include hunk ranges, three context lines, and missing-final-newline markers;
  preserve LF/CRLF payloads without added blank lines or Rich markup processing.
  Use a bounded shortest-path matcher with common-prefix/suffix trimming and
  a complete middle-replacement fallback for expensive searches.
- Repair strategies must return strings. Preserve the current text when a
  strategy raises or returns another type, record its error, and continue with
  later strategies. Close fresh coroutine results without running them.
- Align confidence scores with JavaScript using Unicode code-point lengths and
  exact half-up rounding. Verbose CLI output includes discarded repair steps
  when repair fails; JSON output retains the repair-result shape.
- Validate and copy strategy selections; reject unknown names and malformed
  lists before repair or provider calls, including valid input and empty batches.
  Expose selected names in execution order as `guard.strategy_names`. CLI empty
  selections disable repair; invalid names and empty comma-list elements exit 2
  before input is read. This replaces silently ignoring misspelled names.
- Align CLI argument, stream, file, encoding, and exit-code behavior with
  JavaScript. Preserve CRLF/BOM source text with strict UTF-8, accept all format
  aliases without changing their spelling, add `-h`, route missing-command help
  to stderr with exit 2 across supported Click versions, and normalize
  non-finite JSON report values to null. Valid input no longer produces a retry
  prompt. Operational failures produce concise stderr diagnostics.
- Validate guard formats and repair limits on construction. Preserve explicit
  format overrides, reject empty strings consistently, and use the same Unicode
  trimming rules as JavaScript. Validate batch formats even with no inputs.
- Validate generation retry limits and callbacks before calling a provider.
  Reject non-string provider results without retrying. The async wrapper now
  accepts synchronous providers and observers; the sync wrapper rejects async
  callbacks and closes fresh coroutine results instead of discarding them.
  Preserve explicitly supplied guards and observers even when they are falsey.
- TOML now uses the same private 1.1 parser as JavaScript, including omitted
  seconds, new escapes, and multiline inline tables. Return dates/times as
  strings, preserving fractional digits and offsets without native date-object
  precision loss. Validate calendar/clock fields and normalize CRLF to LF.
  Reject bare CR and invalid Unicode. Remove the tomli runtime dependency.
- YAML now uses the same bundled parser and explicit 1.2 core profile as the
  JavaScript port. `yes`/`on`, dates, numeric underscores, and sexagesimal values
  are strings; leading-zero integers are decimal. Preserve decoded string keys
  and reject duplicate keys, extended/custom tags, unsupported directives,
  cyclic aliases, and excessive alias amplification. Merge keys remain literal.
- Python preserves native numeric precision and alias identity through a graph
  bridge running in thread-local QuickJS-NG contexts, reset after a fork. Node
  is not required at runtime. PyYAML moves to development-only comparisons.
- Schema regexes now use ECMAScript through the `quickjs-ng` dependency,
  replacing Python regex semantics. Named captures use `(?<name>...)`; native
  `jsonschema` classes remain unchanged. Contexts and bounded compiled-pattern
  caches are isolated by thread and reset after a fork.

### Added

- Top-level `repair(..., report=True)` returns a repair result and detailed
  report. Preserve the default plain result and positional format argument.
  Add shared public-helper benchmarks and run repair contracts through both
  guard and module entry points.
- `SchemaEvaluationError` reports non-progressing schema references and stack
  exhaustion with parsed data, the original schema, format, and cause. Stop
  guarded generation immediately. Isolate active-reference tracking per call
  and thread; normalize recursion failures from native resolver extensions.
- `invalidate_schema(schema)` marks an edited root for subsequent validation,
  matching JavaScript's explicit cache-control API. Python already evaluates
  schemas on every call. Shared mutation workflows cover nested constraints,
  references, literal targets, failure recovery, and all validation entry points.
- Exact shared diff contracts with forward/reverse patch checks, independent
  Git application, minimal-edit checks, and sparse/repeated/disjoint benchmarks.
- `RepairReport.candidate_text` exposes the last attempted text after a failed
  repair; `StrategyApplication.error` records failed calls. Shared repair
  contracts check rollback, fallback passes, async returns, and report metadata.
- Shared real-process CLI contracts for flags, streams, files, invalid inputs,
  large pipes, and JSON reports. Add slow-byte-stream and broken-pipe checks,
  a cross-port subprocess gate, and fresh-process wall-time benchmarks.
- Shared configuration fixtures and a cross-port gate checking error categories,
  provider/observer call counts, metadata, inheritance, and numeric limits.
- Benchmarks for format spelling/padding and empty-to-1,000-item batches with
  inherited or overridden guard formats.
- Shared TOML fixtures, generated document/schema checks, date and scalar
  benchmarks, and reproducible private-parser/embedded-engine freshness gates.
- Shared YAML fixtures, generated document/data checks, alias-boundary and
  scaling benchmarks, engine-source freshness gates, and standalone wheel
  assets with the YAML parser's ISC license.
- Shared Python-number fixtures, generated base/float/unary literal checks,
  and numeric parsing/scaling benchmarks. Cover zero signs, overflow, underflow,
  malformed tokens, and retry/batch failure categories in both ports.
- Shared Python-string fixtures, generated literal/decoded-data checks, and
  escape, raw-string, triple-quote, and adjacent-literal scaling benchmarks.
  Document the JavaScript literal subset and native tuple differences.
- Benchmark `--clock wall|cpu` selection, process CPU timing, and logical-CPU/
  system-load observations. Preserve older wall-time reports, reject mixed-clock
  latency comparisons, and add an opt-in `--fail-on-incomparable` CI gate.
- Shared comparison fixtures and deterministic clock/metadata checks, including
  unsupported load readings, malformed reports, and portable count arguments.
- ECMAScript pattern, property-pattern, and regex-format parity checks,
  explicit Unicode/capture/anchor fixtures, generated regex diagnostics, and
  property-map scaling benchmarks.
- Shared schema-format assertions for dates, times, email/host/IP addresses,
  URIs, UUIDs, pointers, durations, Base64, and numeric formats. Python now
  enforces these without optional dependencies or global checker changes.
- Shared format fixtures, generated schema-format diagnostic checks, and
  fresh/reused benchmark cases.
- `ValidationResult.parse_error` distinguishes parser failures from schema
  failures even when the parsed value is `None`.
- Exported `Schema` type for JSON Schema dictionaries and boolean schemas
  throughout the public API.
- A shared Python/JavaScript parity corpus, checked in each test suite,
  a cross-checkout parity command, and repeatable JSON benchmark output.

### Fixed

- Round benchmark microsecond timings half up in both ports, including CPU-time
  results at half-step boundaries.
- Keep property-pattern captures independent, recognize empty patterns when
  discovering additional properties, and escape lone surrogate keys in paths.
- Require complete format values, reject multiline Base64, enforce signed
  64-bit integer limits, and handle offset leap seconds consistently.
- Reject bare `NaN`, `Infinity`, and `-Infinity` in JSON parsing and CLI JSON
  files. Repair nonstandard values to `null`, then report remaining schema
  failures consistently with JavaScript. Preserve native parsing in other formats.
- Scan bare value and boolean repairs in linear time, preserve escaped JSON
  strings, and avoid rewriting fragments of other atoms. Add signed NaN and
  positive Infinity repairs.
- Treat method- and prototype-named properties as literal data in shared
  `const`, `enum`, and `uniqueItems` checks. Extend the parity corpus and
  benchmarks with direct strategy workloads and a seeded parsing/repair checker.
- Preserve repaired text, parsed data, strategy history, and schema errors when
  syntax repair succeeds but the data still fails schema validation.
- Return `None` from `parse()` for schema-accepted nulls, and raise
  `SchemaValidationError` for schema-rejected nulls and repaired schema failures.
- Count rejected nulls as schema failures in batch summaries, and include
  repairs from schema-invalid outputs in batch and generation statistics.
- Give guarded-generation retries the repaired document and remaining schema
  errors. Stop redundant repair work on parsed documents or unchanged text.
- Quote special property names in validation paths, distinguish numeric object
  keys from array indexes, and sort mixed YAML/Python mapping keys without
  raising a `TypeError`.
- Inherit the supplied guard's format in batch helpers unless explicitly
  overridden, matching JavaScript behavior.
- Round batch success rates half up in both ports, including exact ties.
- Expand parity checks and benchmarks to cover diagnostic values, escaped
  property names, prototype-named dictionary keys, and batch summaries.
- Add shared regression fixtures for explicit `__proto__` property and pattern
  schemas, references, closed objects, and nested applicators. Add a seeded
  cross-port schema generator for repeatable comparisons of validation decisions.
- Preserve instance and schema paths for boolean `False` subschemas with older
  `jsonschema` versions. Use native diagnostics when the dependency supports
  them, without patching its validator classes or changing caller schemas.
- Handle boolean schemas, forbidden properties, tuple items, and root array
  schemas in retry prompts and guarded-generation feedback. Compare complete
  retry prompts in the shared corpus.
- Omit ignored `$ref` sibling assertions from retry summaries so feedback agrees
  with Draft 7 validation. Label referenced property schemas explicitly.
- Extend shared fixtures, generated schema comparisons, and benchmarks with
  property/schema dependencies and Draft 7 reference sibling behavior.
- Add shared coverage for independent schemas with reused root and nested IDs,
  recursive references, and fresh-versus-reused schema workflows.
  Benchmarks now distinguish reused schema objects from freshly cloned schemas.
- Add shared coverage for prototype-named relative resource IDs and explicit
  reference targets, including recursion and fresh schema compilation. Check
  that missing resources and pointer properties do not resolve by inheritance.
- Cover anonymous schemas with parent-relative, rooted, and local resource
  names, ensuring internal compilation bases do not alias caller resources.
- Preserve false-subschema instance and schema paths when references select
  schemas inside const, enum, default, examples, or extension annotations.
  Keep literal comparisons and caller-owned documents intact, including across
  embedded resources and recursive references.
- Add shared annotation fixtures and generated comparisons covering `$async`
  metadata, reference targets inside metadata and literal data, synchronous
  validation results, repaired schema failures, and batch summaries.
- Add generated diagnostic checks with independently tracked instance paths
  and values via `benchmarks.check_schema_fuzz --diagnostics`, plus shared
  fixtures and benchmarks for schemas referenced from literal values.
- Expand resource-discovery regressions to cover ignored annotation IDs,
  later-draft anchors, legacy fragment IDs, reference siblings, and pointer
  scopes. Add explicit missing-resource expectations to the shared corpus and
  benchmarks, and generated resource checks via `--resources`.
- Discover IDs in mixed property/schema dependency maps regardless of entry
  order with older `referencing` versions. Preserve assertions, pointer targets,
  false-schema diagnostics, literal data, and caller schemas through a narrow
  fallback after native discovery fails. Keep successful native calls unchanged.
- Add shared mixed-dependency fixtures and fresh/reused benchmarks, and extend
  generated resource checks with mixed dependency declarations.
- Compare shared fixtures and cross-port output using JSON types instead of
  Python's boolean/number equality. Share these checks with the schema generator
  and report the first differing path. Add typed mismatch regressions and
  shared numeric-encoding, negative-zero, and boolean/number fixtures.
- Resolve URI-encoded pointer prefixes and references to valid plain-name
  anchors when the native resolver fails. Combine fragment and dependency
  compatibility in shared document views, preserving literal targets and
  false-schema locations without changing caller schemas.
- Add shared encoded-reference and percent-named resource fixtures, fresh-schema
  benchmarks, and generated validity/path/value checks via `--fragments`.
- Distinguish schemas, schema maps, and pointer-selected data in compilation
  views. Keep dependency triggers named `$id` out of URI scope, and prevent
  annotation IDs after `items` or `dependencies` from changing pointer scope.
  Preserve real descendant IDs, whole-map schema targets, literal comparisons,
  boolean diagnostics, caller ownership, repairs, and generation feedback.
- Establish pointer roles lazily on the first lookup so an annotation ID cannot
  silently redirect validation to an existing resource. Keep pointer frames
  separate when a whole map or data value becomes a schema, including repeated
  lookups and `then`/`else` branches with real IDs.
- Add shared scope regressions and benchmarks, plus independently expected
  generated scope/diagnostic checks via `--scopes`.
- Reduce repeated schema copying for pointer-selected literals. Reuse the
  prepared view within each lookup frame and defer weak-cache creation while
  retaining fresh traversal frames, resource scopes, and source diagnostics.
- Add repeatable `--case NAME` benchmark selection for targeted profiling,
  preserving fixture order and rejecting unknown names before producing output.
- Enforce RFC 6901 array-index syntax during reference lookup. Reject leading
  zeros, signs, whitespace, non-ASCII digits, and missing indexes with native
  reference errors. Preserve literal object keys, encoded pointers, resource
  scopes, false-schema diagnostics, and caller-owned arrays.
- Expand shared fixtures, benchmarks, and generated fragment checks with
  canonical and malformed array indexes, including nested resource arrays.
- Reject reference targets that are null, numeric, string, or array values with
  native `Unresolvable` errors, matching JavaScript. Reject traversal through
  scalars and booleans while preserving boolean-schema validity, false-schema
  diagnostics, literal data, and embedded-resource scopes.
- Add shared target-type fixtures and benchmarks, and extend generated fragment
  checks with invalid targets and scalar/boolean traversal.
- Apply nested resource IDs while `if`, `contains`, `not`, and later `oneOf`
  alternatives evaluate subschemas. Delegate native keyword behavior through
  a local Draft 7 extension, retaining source diagnostics, explicit dialect
  declarations, reference-sibling rules, and native global validator state.
- Add evaluation-scope regressions, shared fixtures and benchmarks, and seeded
  validity checks via `benchmarks.check_schema_fuzz --evaluation`.
- Add `benchmarks.compare` to compare saved timing reports by case and schema
  lifetime. Validate report structure, identify changed conditions and added or
  removed cases, classify unrounded changes against a configurable threshold,
  and optionally fail a CI gate while retaining the JSON report. Share explicit
  comparison fixtures and cross-runtime checks with JavaScript.
- Check `multipleOf` using exact arithmetic over parsed numbers' decimal
  representations. Accept valid decimals such as `0.3` with step `0.1` and
  `2.01` with step `0.01`, reject nearby nonmultiples without a tolerance, and
  handle extreme finite exponents without floating-point quotient overflow.
  Preserve integer precision, diagnostics, literal data, and caller ownership.
- Add shared numeric fixtures, fresh/reused benchmarks, repair/batch coverage,
  and generated numeric checks via `benchmarks.check_schema_fuzz --numeric`.

## [2.1.2] - 2026-07-15

### Changed

- Refreshed the locked dependency set for the 2.1.2 maintenance release.

## [2.1.1] - 2026-05-14

### Fixed

- Resolved ruff check errors in coverage test module (blind exception
  assertion).
- Fixed ruff formatting across project configuration and documentation files.

### Changed

- Test coverage increased to 99.9% (1,328/1,329 statements covered). The single
  remaining uncovered line (`retry.py:28`) is a logistically unreachable dead
  `else` branch.
- Updated `.gitignore` and project documentation.

## [2.1.0] - 2026-05-10

### Added

- **Retry prompt history control**: `retry_prompt(..., include_message_history=False)`
  generates correction prompts that omit the previous model output, useful when
  the original output is too large or distracting for the model's next attempt.
- `guarded_generate(..., include_message_history=False)` and
  `guarded_generate_async(..., include_message_history=False)` for retry loops
  that exclude prior output from generated retry prompts.
- `outputguard retry-prompt --no-message-history` CLI flag.
- Expanded learning guides and documentation covering retry prompt history
  controls.

## [2.0.0] - 2026-05-10

### Added

- **Multi-format support**: Validation and repair now work with JSON, YAML, TOML,
  and Python literal outputs — not just JSON.
- **Auto-detection**: The `auto` format tries JSON → TOML → Python → YAML in
  order, for mixed structured-output workflows.
- **Format aliases**: `yaml`/`yml`, `python-literal`/`python`/`py`/`literal`,
  and `forced-json-off`/`forced_json_off` all resolve to the correct parser.
- **`forced-json-off` mode**: For prompts that explicitly prohibit JSON output,
  this format skips the JSON parser entirely.
- **Guarded generation**: `guarded_generate()` wraps a synchronous LLM callable
  with validation, optional repair, retry feedback, and attempt history.
  `guarded_generate_async()` provides the same workflow for async model clients.
  Provider-agnostic — pass your own callable, no SDK dependency added.
- **`GuardedGenerationError`**: Raised when guarded generation exhausts its retry
  budget (when `throw_on_failure=True`).
- **Batch processing**: `validate_batch()` and `repair_batch()` for validating or
  repairing many model outputs in one call, with `BatchSummary` stats (success
  rate, strategy counts, format breakdown).
- **`outputguard batch` CLI command**: Validate or repair a JSON array of strings
  from the command line.
- Dedicated documentation for formats, API choices, guarded generation, batch
  processing, and CLI usage.
- Guarded-generation and batch-processing code examples.

### Changed

- JSON remains the default format — existing 1.x calls continue to use the
  JSON workflow unless a different `format` is explicitly passed.
- README examples updated to showcase 2.0 workflows (multi-format, guarded
  generation, batch processing).
- Package metadata now advertises YAML and TOML support.
- Test suite expanded to cover format-specific behavior, guarded generation,
  batch APIs, and CLI batch behavior (1,996 tests passing).

### Migration Notes

- All existing calls (`validate_and_repair`, `repair`, `validate`, `parse`)
  continue to default to JSON. No breaking changes for JSON-only users.
- For non-JSON output, pass `format="yaml"`, `format="toml"`,
  `format="python-literal"`, `format="auto"`, or `format="forced-json-off"`.
- Guarded generation adds no LLM provider dependency — pass your own sync or
  async generation callable.
- Batch CLI input must be a JSON array of strings. Use `--input-format` to
  specify how each item should be parsed.

## [1.0.0] - 2026-05-09

### Added

- **`fix_encoding` strategy**: Repairs GPT-2 BPE tokenizer artifacts that corrupt
  JSON output from certain models.
- **`fix_inner_quotes` strategy**: Escapes unescaped double quotes inside JSON
  string values (e.g., `{"text": " "I love sunny days""}`), a pattern observed
  in DeepSeek v3.1 outputs.
- **290-model sweep**: Tested against 290 OpenRouter models across 40+ providers.
  225 returned clean JSON, 61 repaired automatically, 4 excluded (broken API
  responses, not JSON issues). **99%+ success rate**.
- 1,884 tests passing across all categories.
- CI pipeline: GitHub Actions with PyPI publish on `v*` tags using trusted
  publishing (OIDC, no API tokens).

### Fixed

- `strip_fences` now handles unclosed fences from truncated model outputs.
- Resolved all 14 mypy type errors (`@overload` decorators for `repairer.repair()`
  and `OutputGuard.repair()`, union-attr fixes in `guard.py`, assertion for
  non-None data in `parse()`, CLI tuple unpacking).
- Resolved all 60 ruff lint errors (import sorting, unused imports/variables,
  unnecessary f-strings, line length).
- CI fixes: Windows-safe fixture filenames (removed colons), replaced twine
  check, sanitized model slugs.
- Absolute GitHub URLs in README for correct PyPI rendering.

### Changed

- Strategy count increased from 13 to 15 (`fix_encoding`, `fix_inner_quotes`).
- Test suite expanded from 523 to 1,884 tests:
  - 824 tests from 5-agent test team (strategy exhaustive, combinations,
    LLM corpus, API contracts, adversarial/fuzzing).
  - 222 stress battery and real LLM model output tests.
  - 12 real LLM models tested (8 providers, 98% success rate before sweep).
  - 290-model sweep results committed as regression fixtures.
- README updated with per-model results chart and test suite breakdown.
- Added `per-file-ignores` for tests and examples (E501 exempt).

## [0.2.0] - 2026-05-09

### Added

- **`fix_truncated` strategy**: Recovers JSON truncated by token limits by
  closing open brackets, braces, and strings.
- **`fix_ellipsis` strategy**: Replaces `...` placeholders with valid JSON
  values.
- **`fix_unicode` strategy**: Fixes malformed Unicode escape sequences.
- **`fix_booleans` strategy**: Converts Python `True`/`False`/`None` to JSON
  `true`/`false`/`null`.
- **`parse()` convenience function**: Validate → repair → parse in one call.
  Raises `ParseError` or `SchemaValidationError` on failure.
- **Exception hierarchy**: `OutputGuardError` base with `ParseError`,
  `SchemaValidationError`, `RepairError`, `StrategyError`.
- **`RepairReport`**: Detailed observability — diff output, confidence scoring,
  step-by-step strategy tracking.
- `--diff` flag for CLI `validate` and `repair` commands.
- `--verbose` flag showing each strategy's effect.
- Strategy descriptions in `outputguard strategies` table output.
- GitHub Actions CI across Python 3.10–3.13 on Linux, macOS, and Windows.
- `py.typed` marker for PEP 561 type checker support.
- Comprehensive edge-case test suite.
- Examples directory with usage patterns.
- CONTRIBUTING.md guide.

### Changed

- Strategy count increased from 9 to 13.

## [0.1.0] - 2026-05-09

### Added

- Initial release of outputguard.
- **9 core repair strategies**: `strip_fences`, `extract_json`,
  `remove_comments`, `fix_commas`, `fix_quotes`, `fix_keys`, `fix_values`,
  `fix_closers`, `fix_newlines`.
- JSON Schema validation (Draft 7 via `jsonschema`) with detailed error paths
  using JSON path notation (`$.items[0].name`).
- **Validate-and-repair pipeline**: Validate → repair → re-validate loop with
  configurable `max_repair_attempts` (default 3).
- **Two-pass repair engine**: First pass applies all strategies in sequence; if
  that fails, second pass applies one-at-a-time with parse attempts between each.
- **Retry prompt generation**: Human-readable correction prompts for LLM feedback
  loops, including error descriptions, schema summary, and optionally the
  original output.
- **Click CLI**: `validate`, `repair`, `retry-prompt`, and `strategies` commands.
- **Library API**: `validate()`, `repair()`, `validate_and_repair()`,
  `retry_prompt()` module-level convenience functions.
- **Configurable `OutputGuard` class**: Strategy selection, max repair attempts,
  default format.

[Unreleased]: https://github.com/ndcorder/outputguard/compare/v2.1.2...HEAD
[2.1.2]: https://github.com/ndcorder/outputguard/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/ndcorder/outputguard/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ndcorder/outputguard/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ndcorder/outputguard/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/ndcorder/outputguard/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/ndcorder/outputguard/releases/tag/v0.2.0
