# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - Unreleased

### Added

- Format-aware validation and repair for JSON, YAML, TOML, and Python literal
  outputs.
- Format aliases for common user input: `yaml`/`yml`, `python-literal`/`python`
  /`py`/`literal`, and `forced-json-off`/`forced_json_off`.
- `auto` format detection for mixed structured-output workflows.
- `forced-json-off` mode for prompts that explicitly prohibit JSON output.
- `guarded_generate()` for wrapping synchronous LLM calls with generation,
  validation, optional repair, retry feedback, and attempt history.
- `guarded_generate_async()` for the same guarded-generation workflow with async
  model clients.
- `GuardedGenerationError` for guarded generation runs that exhaust their retry
  budget when configured to throw.
- `validate_batch()` for validating many model outputs in one call.
- `repair_batch()` for repairing many model outputs in one call.
- `outputguard batch` CLI command for validating or repairing a JSON array of
  strings.
- Dedicated docs for formats, API choices, guarded generation, batch
  processing, and CLI usage.
- Guarded-generation and batch-processing examples.

### Changed

- JSON remains the default format, so existing 1.x calls continue to use the
  original JSON workflow unless a different `format` is passed.
- README examples now show the main 2.0 workflows instead of only single-output
  JSON repair.
- The batch-processing example now uses the first-class batch APIs.
- Package metadata now advertises YAML and TOML support.
- Test coverage now includes format-specific behavior, guarded generation, batch
  APIs, and CLI batch behavior.

### Compatibility and Migration Notes

- Existing calls such as `validate_and_repair(text, schema)`, `repair(text)`,
  `validate(text, schema)`, and `parse(text, schema)` continue to default to
  JSON.
- To validate non-JSON output, pass `format="yaml"`, `format="toml"`,
  `format="python-literal"`, `format="auto"`, or `format="forced-json-off"`.
- Guarded generation does not add an LLM provider dependency. Pass your own sync
  or async generation callable.
- Batch CLI input must be a JSON array of strings. Use `--input-format` to choose
  how each item should be interpreted.
- For CI and evals, prefer explicit formats and strict validation so invalid
  outputs fail loudly.

### Verification

- Python tests: 1,996 passing.
- Static checks: `ruff check`, `ruff format --check`, and `mypy`.

## [0.2.0] - Unreleased

### Added
- `fix_truncated` strategy: recovers JSON truncated by token limits
- `fix_ellipsis` strategy: replaces `...` placeholders with valid JSON
- `fix_unicode` strategy: fixes malformed Unicode escape sequences
- `fix_booleans` strategy: converts Python True/False/None to JSON true/false/null
- `parse()` convenience function: validate-repair-parse in one call, raises on failure
- `OutputGuard.parse()` method with same behavior
- Exception hierarchy: `OutputGuardError`, `ParseError`, `SchemaValidationError`, `RepairError`
- `RepairReport` with diff output, confidence scoring, and step-by-step strategy tracking
- `--diff` flag for CLI validate and repair commands
- `--verbose` flag for CLI showing each strategy's effect
- Strategy descriptions shown in `outputguard strategies` table
- GitHub Actions CI (Python 3.10-3.13, Linux/macOS/Windows)
- `py.typed` marker for PEP 561
- Comprehensive edge-case test suite
- Examples directory with usage patterns
- CONTRIBUTING.md guide

## [0.1.0] - 2025-01-01

### Added
- Initial release
- 9 core repair strategies: strip_fences, extract_json, remove_comments, fix_commas, fix_quotes, fix_keys, fix_values, fix_closers, fix_newlines
- JSON Schema validation with detailed error paths
- Validate-and-repair pipeline
- Retry prompt generation for LLM feedback loops
- Click CLI with validate, repair, retry-prompt, and strategies commands
- Library API: validate(), repair(), validate_and_repair(), retry_prompt()
- Configurable OutputGuard class with strategy selection
