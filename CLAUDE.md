# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

outputguard is a Python library (3.10+) that validates, repairs, and retries malformed LLM structured output. It supports JSON, YAML, TOML, Python literals, and auto-detection. Published on PyPI, built with Hatchling.

## Commands

```bash
# Setup
uv sync --dev

# Tests
uv run pytest tests/ -v --tb=short
uv run pytest tests/test_strategies/ -v          # strategy tests only
uv run pytest tests/test_stress.py -v             # stress/fuzz tests
uv run pytest tests/test_api_contracts.py -v       # public API contract tests
uv run pytest -k "test_name" -v                   # single test
uv run pytest tests/ --cov=outputguard --cov-report=term-missing  # with coverage

# Lint & format
uv run ruff check .                                # lint
uv run ruff check . --fix                          # lint + autofix
uv run ruff format --check .                       # check formatting
uv run ruff format .                               # apply formatting

# Type check
uv run mypy outputguard/ --ignore-missing-imports

# CLI
uv run outputguard validate INPUT -s SCHEMA
uv run outputguard repair INPUT
uv run outputguard retry-prompt INPUT -s SCHEMA
uv run outputguard batch INPUT -s SCHEMA --repair
uv run outputguard strategies                      # list all strategies

# Build
uv build
```

## Architecture

The package is flat under `outputguard/` with no `src/` layout. The public API lives in `__init__.py` as module-level convenience functions (`validate`, `repair`, `validate_and_repair`, `parse`, `retry_prompt`) that delegate to a default `OutputGuard` instance.

### Core pipeline

**`guard.py` — `OutputGuard`**: The stateful orchestrator. Holds configuration (strategy list, max repair attempts, default format). Its `validate_and_repair` method runs the core loop: validate → if invalid, repair → re-validate, up to `max_repair_attempts` (default 3). `parse()` is the strict variant that raises `ParseError` or `SchemaValidationError` on failure.

**`validator.py`**: Parses text via `formats.parse_document`, then validates against JSON Schema (Draft 7 via `jsonschema`). Returns `ValidationResult` with structured `ValidationError` objects using JSON path notation (`$.items[0].name`).

**`repairer.py`**: Two-pass repair engine. First pass applies ALL strategies in sequence, then tries parsing. If that fails, second pass applies one-at-a-time with parse attempts between each. Non-JSON formats (YAML/TOML/Python) skip the first pass and only do one-at-a-time. Returns `RepairResult`, optionally with a `RepairReport` for observability.

**`formats.py`**: Format abstraction layer. Normalizes format aliases (`yml`→`yaml`, `forced-json-off`→`auto`), parses documents via stdlib/PyYAML/tomllib. The `auto` format tries JSON→TOML→Python→YAML in order.

**`retry.py`**: Generates human-readable correction prompts for the LLM, including error descriptions, schema summary, and optionally the original output. The `include_message_history` flag controls whether the original output is appended.

**`generation.py`**: `guarded_generate` / `guarded_generate_async` — provider-agnostic retry orchestration. Takes a `generate` callable (sync or async), runs prompt→validate→repair→retry_prompt loop with `on_attempt` observer hooks. `throw_on_failure` controls exception vs return semantics.

**`batch.py`**: `validate_batch` / `repair_batch` with `BatchSummary` stats (success rate, strategy counts, format breakdown).

### Strategies

`outputguard/strategies/` contains 15 repair strategies, each a module with `NAME`, `DESCRIPTION`, and `apply(text) -> text`. The registry in `strategies/__init__.py` defines `ALL_STRATEGIES` as an ordered list — **order matters** (encoding fixes first, structural fixes last). Strategy names: `fix_encoding`, `strip_fences`, `extract_json`, `remove_comments`, `fix_commas`, `fix_quotes`, `fix_keys`, `fix_values`, `fix_booleans`, `fix_truncated`, `fix_ellipsis`, `fix_unicode`, `fix_inner_quotes`, `fix_closers`, `fix_newlines`.

### Key types (all in `models.py`)

- `ValidationResult` — `valid`, `data`, `errors`, `repaired`, `strategies_applied`, `original_text`, `repaired_text`, `format`
- `RepairResult` — `repaired`, `text`, `strategies_applied`, `parse_error`, `format`
- `ValidationError` — `message`, `path` (JSON path), `schema_path`, `value`

### Exception hierarchy (in `exceptions.py`)

`OutputGuardError` → `ParseError`, `SchemaValidationError`, `RepairError`, `StrategyError`

## Test Structure

The test suite has 2,001 tests. Key test files:

- `test_api_contracts.py` — public API surface and return type contracts
- `test_llm_corpus.py` — 288 real LLM model outputs (the largest test file)
- `test_strategy_exhaustive.py` — exhaustive per-strategy edge cases
- `test_adversarial.py` — adversarial/pathological inputs
- `test_combinations.py` — multi-strategy interaction tests
- `test_strategies/` — unit tests per strategy module
- `test_formats.py` — YAML/TOML/Python literal parsing and repair
- `test_guarded_generate.py` — guarded generation with mock LLM callables

Fixtures live in `tests/fixtures/` (`simple_schema.json`, `nested_schema.json`). Common schema fixtures are also defined in `tests/conftest.py`.

## CI

GitHub Actions (`.github/workflows/ci.yml`): tests run on matrix of `{ubuntu, macos, windows} × {3.10, 3.11, 3.12, 3.13}`. Lint job runs ruff + mypy. Publish to PyPI triggers on `v*` tags.

## Conventions

- Ruff config: line length 100, target Python 3.10, rules `E,F,I,W,UP,B,SIM`. Tests/examples exempt from E501.
- Double quotes (`quote-style = "double"`).
- No runtime dependencies beyond click, jsonschema, PyYAML, rich, and tomli (3.10 only).
- Each strategy module exports `NAME: str`, `DESCRIPTION: str`, `apply(text: str) -> str`.
- `format` parameter appears throughout the API — it's always a string matching `SUPPORTED_FORMATS` and gets normalized via `formats.normalize_format()`.

<!-- headroom:learn:start -->
## Headroom Learned Patterns
*Auto-generated by `headroom learn` on 2026-05-14 — do not edit manually*

### Learned: environment
- Working test command: `python -c "import subprocess; r = subprocess.run(['python', '-m', 'pytest', 'tests/test_stress.py', '-v', '--tb=short'], capture_output=True, text=True, cwd='/Users/kexxt/code-opensource/outputguard')`

<!-- headroom:learn:end -->
