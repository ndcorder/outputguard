# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/ndcorder/outputguard/compare/v2.1.1...HEAD
[2.1.1]: https://github.com/ndcorder/outputguard/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ndcorder/outputguard/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ndcorder/outputguard/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/ndcorder/outputguard/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/ndcorder/outputguard/releases/tag/v0.2.0
