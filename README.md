# outputguard

**Stop wrestling with broken LLM structured output.** Validate, repair, and retry — automatically.

[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://github.com/ndcorder/outputguard)
[![CI](https://github.com/ndcorder/outputguard/actions/workflows/ci.yml/badge.svg)](https://github.com/ndcorder/outputguard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1,996-brightgreen)](#tested-against-288-real-llm-models)

---

## The Problem

LLMs produce broken structured output constantly. JSON is the common case, but models also return YAML, TOML, Python-style literals when forced JSON is off, markdown fences, comments, trailing commas, `NaN`, truncated objects, and helpful commentary around the data you asked for. Every AI application ends up writing the same brittle parser + `try/except` + regex gauntlet.

## The Solution

```python
import outputguard

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    },
    "required": ["name", "age"]
}

# Typical LLM output — fenced, trailing comma, single quotes
llm_output = '''```json
{'name': 'Alice', 'age': 30,}
```'''

result = outputguard.validate_and_repair(llm_output, schema)
print(result.valid)              # True
print(result.data)               # {'name': 'Alice', 'age': 30}
print(result.strategies_applied) # ['strip_fences', 'fix_quotes', 'fix_commas']
```

Fifteen repair strategies, JSON Schema validation, retry prompt generation, and a CLI — now for JSON, YAML, TOML, Python literals, and auto-detected forced-JSON-off output.

## Installation

```bash
pip install outputguard
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add outputguard
```

## Documentation

Start with the README for a fast overview, then use the focused guides when you
need exact behavior, API signatures, or command examples:

- [API guide](docs/api.md) - choose the right function and understand result
  objects.
- [Formats guide](docs/formats.md) - JSON, YAML, TOML, Python literals, `auto`,
  and `forced-json-off`.
- [Guarded generation guide](docs/guarded-generation.md) - wrap an LLM call with
  validation, repair, retry, and observability.
- [Batch processing guide](docs/batch-processing.md) - validate or repair many
  outputs in one call or from the CLI.
- [CLI guide](docs/cli.md) - commands, flags, examples, and exit codes.
- [Changelog](CHANGELOG.md) - release notes and 2.0 migration notes.

## What's New in 2.0

OutputGuard 2.0 keeps JSON as the default path, so existing 1.x code continues
to work without passing new options. The new capabilities are opt-in:

- Format-aware validation and repair with `format="json"`, `"yaml"`, `"toml"`,
  `"python-literal"`, `"auto"`, and `"forced-json-off"`.
- Guarded generation helpers that call your LLM function, validate the response,
  optionally repair it, and retry with structured feedback.
- Batch APIs and a `batch` CLI command for evals, logs, and offline audits.
- More explicit reports and errors for failed guarded-generation runs.

## Choosing the Right API

| Goal | API |
| --- | --- |
| Validate and repair one model output | `validate_and_repair()` |
| Repair without a full validation workflow | `repair()` |
| Check validity only | `validate()` |
| Get parsed Python data or raise | `parse()` |
| Build a validation-aware retry loop | `retry_prompt()` |
| Wrap an LLM generation function | `guarded_generate()` / `guarded_generate_async()` |
| Validate many outputs | `validate_batch()` |
| Repair many outputs | `repair_batch()` |

## Quick Start

### Validate & Repair

The most common pattern — validate against a schema, auto-repair if broken, get clean data back:

```python
import outputguard

result = outputguard.validate_and_repair(llm_output, schema)

if result.valid:
    process(result.data)                  # Clean, validated dict
    if result.repaired:
        log(result.strategies_applied)    # What was fixed
else:
    handle_errors(result.errors)          # Detailed error paths
```

### Repair Only

When you just need parseable structured output and don't have a schema:

```python
result = outputguard.repair(broken_json)
print(result.text)                # Clean JSON string by default
print(result.strategies_applied)  # ['fix_booleans', 'fix_commas']
```

### Validate Only

Check structured output against a schema without attempting repair:

```python
result = outputguard.validate(llm_output, schema)
for error in result.errors:
    print(f"{error.path}: {error.message}")
    # $.age: 'thirty' is not of type 'integer'
```

### Retry Loop

When repair is not enough, generate a correction prompt and send it back to the LLM:

```python
import outputguard

def get_structured_output(llm, prompt, schema, max_retries=3):
    for attempt in range(max_retries + 1):
        raw = llm.generate(prompt)
        result = outputguard.validate_and_repair(raw, schema)

        if result.valid:
            return result.data

        # Generate a targeted correction prompt
        prompt = outputguard.retry_prompt(raw, schema, result.errors)

    raise RuntimeError("Failed to get valid output")
```

The retry prompt tells the LLM exactly what went wrong — which fields are missing, which types are incorrect, and what the schema expects. Works with any LLM provider.

### Guarded Generation

For production retry loops, use `guarded_generate()` to wrap any LLM client without adding provider dependencies:

```python
import outputguard

result = outputguard.guarded_generate(
    prompt="Return a user object as JSON",
    schema=schema,
    max_retries=3,
    generate=lambda prompt, context: llm.generate(prompt),
)

if result.valid:
    print(result.data)
    print(len(result.attempts))
else:
    print(result.errors)
```

`guarded_generate()` validates each generation, repairs when possible, feeds targeted retry prompts back to the generator, and returns every attempt for observability. Pass `repair=False` for strict validation-only loops or `throw_on_failure=True` when invalid output should raise `GuardedGenerationError`.

Async clients can use `guarded_generate_async()` with the same options.

### Supported Formats

JSON remains the default, so existing code keeps working. Pass `format=` to parse and repair other data formats:

```python
yaml_result = outputguard.validate_and_repair(
    "```yaml\nname: Alice\nage: 30\n```",
    schema,
    format="yaml",
)

toml_data = outputguard.parse('name = "Alice"\nage = 30', schema, format="toml")
python_data = outputguard.parse("{'name': 'Alice', 'age': 30}", schema, format="python")

# Use auto or forced-json-off when the model is not constrained to JSON.
auto_data = outputguard.parse("name: Alice\nage: 30", schema, format="forced-json-off")
```

Supported input formats are `json`, `yaml`/`yml`, `toml`, `python`/`python-literal`, `auto`, and `forced-json-off`.

### Batch Processing

Use batch helpers when validating fixture sets, eval outputs, or logs:

```python
batch = outputguard.validate_batch(outputs, schema, repair=True, format="auto")
print(batch.summary)
# BatchSummary(total=..., valid=..., invalid=..., repaired=..., ...)

repaired = outputguard.repair_batch(outputs)
print(repaired.summary.strategy_counts)
```

### CLI

```bash
# Validate JSON against a schema
outputguard validate output.json -s schema.json

# Validate YAML, TOML, Python literal, or auto-detected output
outputguard validate output.yaml -s schema.json --input-format yaml
outputguard validate output.toml -s schema.json --input-format toml
outputguard validate output.txt -s schema.json --input-format forced-json-off

# Validate with auto-repair
outputguard validate output.json -s schema.json --repair

# Repair only (no schema)
outputguard repair output.json
outputguard repair output.yaml --input-format yaml

# Validate a JSON array of output strings
outputguard batch outputs.json -s schema.json --repair -f json

# Pipe from stdin
echo '{name: "Alice", age: 30,}' | outputguard repair -

# Generate a retry prompt
outputguard retry-prompt output.json -s schema.json

# List all repair strategies
outputguard strategies
```

## What It Fixes

Fifteen strategies, applied in order. Most target JSON-family malformations; generic strategies such as `strip_fences` also repair fenced YAML, TOML, and Python literal output without converting it to JSON.

| # | Strategy | Before | After |
|---|---|---|---|
| 1 | `fix_encoding` | `Ċ{ĊĠ"a":Ġ1Ċ}` | `{"a": 1}` |
| 2 | `strip_fences` | `` ```json\n{"a": 1}\n``` `` | `{"a": 1}` |
| 3 | `extract_json` | `Sure! Here's the JSON: {"a": 1} Let me know!` | `{"a": 1}` |
| 4 | `remove_comments` | `{"a": 1} // a comment` | `{"a": 1}` |
| 5 | `fix_commas` | `{"a": 1, "b": 2,}` | `{"a": 1, "b": 2}` |
| 6 | `fix_quotes` | `{'a': 'hello'}` | `{"a": "hello"}` |
| 7 | `fix_keys` | `{a: 1, b: 2}` | `{"a": 1, "b": 2}` |
| 8 | `fix_values` | `{"a": NaN, "b": Infinity}` | `{"a": null, "b": null}` |
| 9 | `fix_booleans` | `{"a": True, "b": None}` | `{"a": true, "b": null}` |
| 10 | `fix_truncated` | `{"a": 1, "b": "hel` | `{"a": 1, "b": "hel"}` |
| 11 | `fix_ellipsis` | `{"items": [1, 2, ...]}` | `{"items": [1, 2]}` |
| 12 | `fix_unicode` | `{"a": "\u00"}` | `{"a": "�"}` |
| 13 | `fix_inner_quotes` | `{"a": " "hello" "}` | `{"a": " \"hello\" "}` |
| 14 | `fix_closers` | `{"a": [1, 2, 3` | `{"a": [1, 2, 3]}` |
| 15 | `fix_newlines` | `{"a": "line1↵line2"}` | `{"a": "line1\nline2"}` |

## Tested Against 288 Real LLM Models

We tested outputguard against **every text-generation model on OpenRouter** — 288 models across 40+ providers.

**Result: 100% success rate.** Every model's output was either valid JSON or successfully repaired.

| | Count |
|---|---|
| Models tested | **288** |
| Valid immediately | 225 (78%) |
| Repaired by outputguard | 63 (22%) |

The 63 repaired outputs were fixed automatically — mostly `strip_fences` (markdown code fences are the #1 LLM JSON issue), plus `extract_json`, `fix_truncated`, and `fix_encoding`.

> *4 models were excluded from testing due to broken API responses (tokenizer corruption, truncated streaming) — not JSON issues.*

<details>
<summary><strong>Highlighted model results</strong> (click to expand)</summary>

| Model | Provider | Result | Fix Applied |
|---|---|---|---|
| GPT-5 Mini | OpenAI | ✅ Clean | — |
| GPT-5 Pro | OpenAI | ✅ Clean | — |
| GPT-4.1 Mini | OpenAI | ✅ Clean | — |
| Claude Sonnet 4.6 | Anthropic | ✅ Clean | — |
| Claude Opus 4.7 | Anthropic | ✅ Clean | — |
| Claude Haiku 4.5 | Anthropic | 🛠️ Repaired | `strip_fences` |
| Gemini 2.5 Flash | Google | ✅ Clean | — |
| Gemini 2.5 Pro | Google | 🛠️ Repaired | `strip_fences` |
| Gemini 3.1 Flash Lite | Google | ✅ Clean | — |
| Grok 4.1 Fast | xAI | ✅ Clean | — |
| Grok 4.3 | xAI | ✅ Clean | — |
| Mistral Medium 3.5 | Mistral | ✅ Clean | — |
| Mistral Large | Mistral | ✅ Clean | — |
| DeepSeek v4 Pro | DeepSeek | ✅ Clean | — |
| DeepSeek v3.2 | DeepSeek | 🛠️ Repaired | `strip_fences` |
| Llama 4 Maverick | Meta | ✅ Clean | — |
| Llama 4 Scout | Meta | 🛠️ Repaired | `strip_fences` |
| Qwen 3.6 Flash | Alibaba | ✅ Clean | — |
| Qwen 3 Max | Alibaba | ✅ Clean | — |
| Kimi K2.6 | Moonshot | ✅ Clean | — |
| GLM 5.1 | Zhipu | ✅ Clean | — |
| Command A | Cohere | ✅ Clean | — |
| Phi-4 | Microsoft | 🛠️ Repaired | `strip_fences` |
| Nova Premier | Amazon | 🛠️ Repaired | `strip_fences` |
| Seed 1.6 | ByteDance | ✅ Clean | — |
| Mercury 2 | Inception | ✅ Clean | — |

</details>

> All 288 raw model outputs are committed as [test fixtures](https://github.com/ndcorder/outputguard/tree/master/tests/fixtures/real_outputs). Run `python -m tests.real_model_runner sweep` to re-test against every model yourself.

### Test Suite

**1,996 tests** across 9 testing dimensions:

| Category | Tests | What it covers |
|---|---|---|
| Strategy exhaustive | 159 | Every strategy pushed to edge cases |
| Adversarial & fuzzing | 286 | 141 chaotic inputs, concurrency, performance |
| API contracts | 145 | `parse()`, exceptions, reports, CLI, registry |
| LLM corpus | 119 | Real failure patterns from 7 model families |
| Combinations | 115 | Multi-strategy interactions, ordering, idempotency |
| Real model fixtures | 576 | Actual outputs from 288 LLM models |
| Core & integration | 414 | Strategies, validator, repairer, guard, stress |
| Format matrix | 74 | Every public JSON API surface repeated for YAML, TOML, Python literals, auto, aliases, and forced-JSON-off |
| 2.0 orchestration | 10 | Guarded generation, async generation, batch helpers, and batch CLI |

```bash
uv run pytest tests/ -q
# 1,996 passed
```

## Configuration

Use the `OutputGuard` class for fine-grained control over which strategies run:

```python
from outputguard import OutputGuard

# Strict mode — only fix formatting, not content
strict = OutputGuard(
    strategies=["strip_fences", "fix_commas"],
    max_repair_attempts=1,
)
result = strict.validate_and_repair(text, schema)

# Aggressive mode — all strategies, more attempts
aggressive = OutputGuard(
    strategies=None,          # All 15 strategies (default)
    max_repair_attempts=5,
)
result = aggressive.validate_and_repair(text, schema)

# YAML mode — preserves YAML syntax when repairing fenced output
yaml_guard = OutputGuard(format="yaml")
result = yaml_guard.validate_and_repair("```yaml\nname: Alice\nage: 30\n```", schema)
```

## RepairReport

For debugging and observability, `RepairReport` gives you a full breakdown of what happened:

```python
from outputguard.report import RepairReport

report = RepairReport(
    original_text=original,
    final_text=repaired,
    success=True,
    steps=steps,
)

print(report.summary)
# Repaired using 2 strategy(ies): strip_fences, fix_commas

print(report.confidence)   # 0.8 — fewer strategies = higher confidence
print(report.diff)         # Unified diff from original to repaired
print(report.step_diffs()) # Per-strategy diffs for verbose logging
```

**Confidence scoring** is a heuristic from 0.0 to 1.0. It decreases as more strategies are needed and as the text changes more. Useful for deciding whether to trust a repair or escalate to a retry.

## API Reference

### Module-level Functions

| Function | Returns | Description |
|---|---|---|
| `validate(text, schema, format="json")` | `ValidationResult` | Validate structured output against a schema |
| `repair(text, format="json")` | `RepairResult` | Auto-repair malformed structured output |
| `validate_and_repair(text, schema, format="json")` | `ValidationResult` | Validate, repair if needed, re-validate |
| `parse(text, schema, format="json")` | `dict | list | scalar` | Validate, repair, and return parsed data |
| `retry_prompt(text, schema, errors, format="json")` | `str` | Generate a correction prompt for the LLM |
| `guarded_generate(...)` | `GuardedGenerateResult` | Retry an arbitrary generator until output validates |
| `guarded_generate_async(...)` | `GuardedGenerateResult` | Async variant for async LLM clients |
| `validate_batch(texts, schema, ...)` | `BatchValidationResult` | Validate many outputs and return aggregate diagnostics |
| `repair_batch(texts, ...)` | `BatchRepairResult` | Repair many outputs and return aggregate diagnostics |

### Classes

| Class | Description |
|---|---|
| `OutputGuard` | Configurable pipeline with strategy selection, retry limits, and default `format` |
| `GuardedGenerateResult` | Result with `valid`, `data`, `text`, `attempts`, `errors`, `repaired`, `strategies_applied`, `exhausted`, `format` |
| `BatchSummary` | Summary with `total`, `valid`, `invalid`, `repaired`, `parse_failures`, `schema_failures`, `success_rate`, `strategy_counts`, `formats` |
| `ValidationResult` | Result with `valid`, `data`, `errors`, `repaired`, `strategies_applied`, `format` |
| `RepairResult` | Result with `repaired`, `text`, `strategies_applied`, `parse_error`, `format` |
| `ValidationError` | Error detail with `message`, `path`, `schema_path`, `value` |
| `RepairReport` | Detailed report with `diff`, `confidence`, `summary`, `step_diffs()` |

### Exceptions

| Exception | Description |
|---|---|
| `OutputGuardError` | Base exception |
| `ParseError` | Structured output could not be parsed even after repair |
| `SchemaValidationError` | Structured output parsed but does not match the schema |
| `GuardedGenerationError` | `guarded_generate(..., throw_on_failure=True)` could not get valid output |
| `RepairError` | Repair was attempted but failed |
| `StrategyError` | A specific repair strategy encountered an error |

## CLI Reference

```
outputguard [COMMAND] [OPTIONS]
```

| Command | Description |
|---|---|
| `validate INPUT -s SCHEMA` | Validate structured output against a schema |
| `validate INPUT -s SCHEMA --repair` | Validate with auto-repair |
| `validate INPUT -s SCHEMA --input-format yaml` | Validate YAML instead of JSON |
| `repair INPUT` | Repair malformed structured output |
| `repair INPUT --strategies strip_fences,fix_commas` | Repair with specific strategies |
| `repair INPUT --input-format forced-json-off` | Repair auto-detected non-JSON output |
| `batch INPUT -s SCHEMA --repair` | Validate a JSON array of output strings |
| `retry-prompt INPUT -s SCHEMA` | Generate a correction prompt |
| `strategies` | List all available strategies |

All commands accept `--input-format` for the data format, `-f json` for machine-readable command output, `-o FILE` to write to a file, and `-` as INPUT to read from stdin.

## Why outputguard?

| | `json.loads()` + regex | outputguard |
|---|---|---|
| Repair strategies | Roll your own | 15, tested and ordered |
| Schema validation | Separate library | Built in (jsonschema) |
| Retry prompts | Write your own | One function call |
| Retry orchestration | Write a custom loop | `guarded_generate()` / `guarded_generate_async()` |
| Batch processing | Ad hoc scripts | `validate_batch()`, `repair_batch()`, CLI `batch` |
| Confidence scoring | No | Yes |
| Truncated JSON | Breaks | Recovers |
| Tests | Probably zero | **1,996** (incl. 288 real LLM models and format matrix coverage) |
| LLM dependencies | — | None (works with any provider) |
| Footprint | — | Small runtime set: click, jsonschema, PyYAML, rich, plus tomli on Python 3.10 |

outputguard has no opinion about which LLM you use or whether JSON mode is available. It operates on strings and schemas — plug it into OpenAI, Anthropic, local models, or anything else.

## Examples

See the [`examples/`](https://github.com/ndcorder/outputguard/tree/master/examples) directory for complete, runnable scripts:

- **[basic_usage.py](examples/basic_usage.py)** — Core validate/repair workflow
- **[retry_loop.py](examples/retry_loop.py)** — Retry pattern with correction prompts
- **[guarded_generation.py](examples/guarded_generation.py)** — Provider-agnostic guarded generation
- **[custom_pipeline.py](examples/custom_pipeline.py)** — Custom strategy configuration
- **[batch_processing.py](examples/batch_processing.py)** — Process multiple outputs with statistics

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

```bash
git clone https://github.com/ndcorder/outputguard.git
cd outputguard
uv sync --dev
uv run pytest tests/ -v
```

## TypeScript / JavaScript

Looking for a JS/TS version? See **[outputguard-js](https://github.com/ndcorder/outputguard-js)** — same core API shape, TypeScript-native.

## License

[MIT](LICENSE)
