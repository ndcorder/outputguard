# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
