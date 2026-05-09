# outputguard

**Stop wrestling with broken LLM JSON.** Validate, repair, and retry — automatically.

[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://github.com/ndcorder/outputguard)
[![CI](https://github.com/ndcorder/outputguard/actions/workflows/ci.yml/badge.svg)](https://github.com/ndcorder/outputguard/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-1,881-brightgreen)](#tested-against-290-real-llm-models)

---

## The Problem

LLMs produce broken JSON constantly. They wrap it in markdown fences, leave trailing commas, use Python `True`/`False` instead of `true`/`false`, sprinkle in `NaN`, truncate mid-object when they hit token limits, and helpfully add commentary around the JSON you asked for. Every AI application ends up writing the same brittle `json.loads()` + `try/except` + regex gauntlet.

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

Fourteen repair strategies, JSON Schema validation, retry prompt generation, and a CLI — in one tiny package with three dependencies.

## Installation

```bash
pip install outputguard
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add outputguard
```

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

When you just need parseable JSON and don't have a schema:

```python
result = outputguard.repair(broken_json)
print(result.text)                # Clean JSON string
print(result.strategies_applied)  # ['fix_booleans', 'fix_commas']
```

### Validate Only

Check JSON against a schema without attempting repair:

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

### CLI

```bash
# Validate JSON against a schema
outputguard validate output.json -s schema.json

# Validate with auto-repair
outputguard validate output.json -s schema.json --repair

# Repair only (no schema)
outputguard repair output.json

# Pipe from stdin
echo '{name: "Alice", age: 30,}' | outputguard repair -

# Generate a retry prompt
outputguard retry-prompt output.json -s schema.json

# List all repair strategies
outputguard strategies
```

## What It Fixes

Fourteen strategies, applied in order. Each one targets a specific class of LLM JSON malformation:

| # | Strategy | Before | After |
|---|---|---|---|
| 1 | `strip_fences` | `` ```json\n{"a": 1}\n``` `` | `{"a": 1}` |
| 2 | `extract_json` | `Sure! Here's the JSON: {"a": 1} Let me know!` | `{"a": 1}` |
| 3 | `remove_comments` | `{"a": 1} // a comment` | `{"a": 1}` |
| 4 | `fix_commas` | `{"a": 1, "b": 2,}` | `{"a": 1, "b": 2}` |
| 5 | `fix_quotes` | `{'a': 'hello'}` | `{"a": "hello"}` |
| 6 | `fix_keys` | `{a: 1, b: 2}` | `{"a": 1, "b": 2}` |
| 7 | `fix_values` | `{"a": NaN, "b": Infinity}` | `{"a": null, "b": null}` |
| 8 | `fix_booleans` | `{"a": True, "b": None}` | `{"a": true, "b": null}` |
| 9 | `fix_truncated` | `{"a": 1, "b": "hel` | `{"a": 1, "b": "hel"}` |
| 10 | `fix_ellipsis` | `{"items": [1, 2, ...]}` | `{"items": [1, 2]}` |
| 11 | `fix_unicode` | `{"a": "\u00"}` | `{"a": "�"}` |
| 12 | `fix_inner_quotes` | `{"a": " "hello" "}` | `{"a": " \"hello\" "}` |
| 13 | `fix_closers` | `{"a": [1, 2, 3` | `{"a": [1, 2, 3]}` |
| 14 | `fix_newlines` | `{"a": "line1↵line2"}` | `{"a": "line1\nline2"}` |

## Tested Against 290 Real LLM Models

We tested outputguard against **every text-generation model on OpenRouter** — 290 models across 40+ providers.

**Result: 99% success rate** (286/290 models handled correctly)

| | Count |
|---|---|
| Models tested | **290** |
| Valid immediately | 225 (78%) |
| Repaired by outputguard | 61 (21%) |
| Failed | 4 (1%) |

The 61 repaired outputs were fixed automatically — 55 needed `strip_fences`, 4 needed `extract_json`, 2 needed `fix_truncated`. The 4 failures were models that returned corrupted/garbled output (tokenizer issues, not JSON problems).

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

> All 290 raw model outputs are committed as [test fixtures](tests/fixtures/real_outputs/). Run `python -m tests.real_model_runner sweep` to re-test against every model yourself.

### Test Suite

**1,347 tests** across 7 testing dimensions:

| Category | Tests | What it covers |
|---|---|---|
| Strategy exhaustive | 159 | Every strategy pushed to edge cases |
| Adversarial & fuzzing | 286 | 141 chaotic inputs, concurrency, performance |
| API contracts | 145 | `parse()`, exceptions, reports, CLI, registry |
| LLM corpus | 119 | Real failure patterns from 7 model families |
| Combinations | 115 | Multi-strategy interactions, ordering, idempotency |
| Real model fixtures | 580 | Actual outputs from 290 LLM models |
| Core & integration | 414 | Strategies, validator, repairer, guard, stress |

```bash
uv run pytest tests/ -q
# 1,881 passed in 1.52s
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
    strategies=None,          # All 13 strategies (default)
    max_repair_attempts=5,
)
result = aggressive.validate_and_repair(text, schema)
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
| `validate(text, schema)` | `ValidationResult` | Validate JSON against a schema |
| `repair(text)` | `RepairResult` | Auto-repair malformed JSON |
| `validate_and_repair(text, schema)` | `ValidationResult` | Validate, repair if needed, re-validate |
| `retry_prompt(text, schema, errors)` | `str` | Generate a correction prompt for the LLM |

### Classes

| Class | Description |
|---|---|
| `OutputGuard` | Configurable pipeline with strategy selection and retry limits |
| `ValidationResult` | Result with `valid`, `data`, `errors`, `repaired`, `strategies_applied` |
| `RepairResult` | Result with `repaired`, `text`, `strategies_applied`, `parse_error` |
| `ValidationError` | Error detail with `message`, `path`, `schema_path`, `value` |
| `RepairReport` | Detailed report with `diff`, `confidence`, `summary`, `step_diffs()` |

### Exceptions

| Exception | Description |
|---|---|
| `OutputGuardError` | Base exception |
| `ParseError` | JSON could not be parsed even after repair |
| `SchemaValidationError` | JSON parsed but does not match the schema |
| `RepairError` | Repair was attempted but failed |
| `StrategyError` | A specific repair strategy encountered an error |

## CLI Reference

```
outputguard [COMMAND] [OPTIONS]
```

| Command | Description |
|---|---|
| `validate INPUT -s SCHEMA` | Validate JSON against a schema |
| `validate INPUT -s SCHEMA --repair` | Validate with auto-repair |
| `repair INPUT` | Repair malformed JSON |
| `repair INPUT --strategies strip_fences,fix_commas` | Repair with specific strategies |
| `retry-prompt INPUT -s SCHEMA` | Generate a correction prompt |
| `strategies` | List all available strategies |

All commands accept `-f json` for machine-readable output, `-o FILE` to write to a file, and `-` as INPUT to read from stdin.

## Why outputguard?

| | `json.loads()` + regex | outputguard |
|---|---|---|
| Repair strategies | Roll your own | 14, tested and ordered |
| Schema validation | Separate library | Built in (jsonschema) |
| Retry prompts | Write your own | One function call |
| Confidence scoring | No | Yes |
| Truncated JSON | Breaks | Recovers |
| Tests | Probably zero | **1,347** (including real LLM outputs) |
| LLM dependencies | — | None (works with any provider) |
| Footprint | — | 3 deps: click, jsonschema, rich |

outputguard has no opinion about which LLM you use. It operates on strings and schemas — plug it into OpenAI, Anthropic, local models, or anything else.

## Examples

See the [`examples/`](examples/) directory for complete, runnable scripts:

- **[basic_usage.py](examples/basic_usage.py)** — Core validate/repair workflow
- **[retry_loop.py](examples/retry_loop.py)** — Retry pattern with correction prompts
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

Looking for a JS/TS version? See **[outputguard-js](https://github.com/ndcorder/outputguard-js)** — same 13 strategies, same API shape, TypeScript-native.

## License

[MIT](LICENSE)
