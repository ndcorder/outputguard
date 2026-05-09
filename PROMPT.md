# PROMPT — Build outputguard from scratch

You are Claude Code. Build the entire `outputguard` project autonomously. Do NOT ask any questions. Make all decisions yourself. Follow every step below.

---

## Project Summary

**outputguard** validates, repairs, and retries LLM structured outputs. Validates strings against JSON Schema, auto-repairs common LLM JSON malformations (markdown fences, trailing commas, unquoted keys, commentary text, etc.), and supports retry-with-feedback workflows. Works as both a Python library and CLI.

---

## Step 1: Initialize the Project

```bash
cd /Users/kexxt/code-opensource/outputguard
git init
uv init --name outputguard --python 3.10
```

Edit `pyproject.toml`:
- name: `outputguard`
- version: `0.1.0`
- description: `Validate, repair, and retry LLM structured outputs`
- requires-python: `>=3.10`
- dependencies: `click>=8.1`, `jsonschema>=4.20`, `rich>=13.0`
- `[project.scripts]`: `outputguard = "outputguard.cli:cli"`

Add dev dependencies:
```bash
uv add --dev pytest pytest-cov
```

## Step 2: Create Project Structure

```
outputguard/
  __init__.py            # Public API: validate, repair, validate_and_repair, retry_prompt
  cli.py                 # Click CLI
  validator.py           # JSON Schema validation logic
  repairer.py            # Repair pipeline and individual strategies
  strategies/
    __init__.py           # Registry of all strategies
    strip_fences.py       # Remove markdown code fences
    extract_json.py       # Extract JSON from surrounding text
    remove_comments.py    # Strip JS-style comments
    fix_commas.py         # Fix trailing commas
    fix_quotes.py         # Fix single quotes to double quotes
    fix_keys.py           # Quote unquoted keys
    fix_values.py         # Fix NaN, Infinity, undefined
    fix_closers.py        # Balance missing braces/brackets
    fix_newlines.py       # Escape unescaped newlines in strings
  retry.py               # Retry prompt generation
  models.py              # ValidationResult, ValidationError, RepairResult
  guard.py               # OutputGuard class (configurable pipeline)
tests/
  __init__.py
  test_validator.py
  test_repairer.py
  test_strategies/
    __init__.py
    test_strip_fences.py
    test_extract_json.py
    test_remove_comments.py
    test_fix_commas.py
    test_fix_quotes.py
    test_fix_keys.py
    test_fix_values.py
    test_fix_closers.py
    test_fix_newlines.py
  test_retry.py
  test_guard.py
  test_cli.py
  test_integration.py
  fixtures/
    simple_schema.json
    nested_schema.json
```

## Step 3: Implement Models (`models.py`)

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class ValidationError:
    message: str
    path: str           # JSON path, e.g. "$.items[0].name"
    schema_path: str    # Schema path that was violated
    value: Any = None

@dataclass
class ValidationResult:
    valid: bool
    data: dict | list | None = None
    errors: list[ValidationError] = field(default_factory=list)
    repaired: bool = False
    strategies_applied: list[str] = field(default_factory=list)
    original_text: str = ""
    repaired_text: str = ""

@dataclass
class RepairResult:
    repaired: bool
    text: str
    strategies_applied: list[str] = field(default_factory=list)
    parse_error: str | None = None
```

## Step 4: Implement Repair Strategies (`strategies/`)

Each strategy is a module with a function `apply(text: str) -> str`. Each should also have a `NAME: str` constant.

### `strip_fences.py` (Order 1):
- Remove ````json\n...\n```` patterns
- Remove ````\n...\n```` patterns
- Handle ````JSON`, ````jsonc`, ````javascript` variants
- Handle triple backticks with any language tag

### `extract_json.py` (Order 2):
- Find the first balanced `{...}` or `[...]` in the text
- Handle cases like "Here is the JSON:\n{...}\nLet me know if you need changes"
- Use bracket counting to find the matching close bracket
- Return the extracted JSON substring

### `remove_comments.py` (Order 3):
- Remove `// single line comments`
- Remove `/* multi-line comments */`
- Be careful not to remove `://` in URLs or `//` inside strings

### `fix_commas.py` (Order 4):
- Remove trailing commas: `{a: 1,}` → `{a: 1}`
- Handle nested trailing commas
- Handle commas before `]` in arrays

### `fix_quotes.py` (Order 5):
- Replace single-quoted strings with double-quoted: `{'key': 'value'}` → `{"key": "value"}`
- Handle escaped single quotes within strings
- Be careful with apostrophes in values

### `fix_keys.py` (Order 6):
- Add double quotes to unquoted object keys: `{key: "value"}` → `{"key": "value"}`
- Handle keys with underscores, hyphens, dots

### `fix_values.py` (Order 7):
- Replace `NaN` → `null`
- Replace `Infinity` / `-Infinity` → `null`
- Replace `undefined` → `null`
- Only replace when not inside a string

### `fix_closers.py` (Order 8):
- Count open and close braces/brackets
- Append missing closers in correct order
- E.g., `{"a": [1, 2` → `{"a": [1, 2]}`

### `fix_newlines.py` (Order 9):
- Find string values containing literal (unescaped) newlines
- Replace `\n` with `\\n` inside JSON string values

### Registry (`strategies/__init__.py`):
- `ALL_STRATEGIES: list[tuple[str, Callable]]` — ordered list of (name, function) pairs
- `get_strategy(name: str) -> Callable`
- `get_strategies(names: list[str] | None) -> list[tuple[str, Callable]]` — returns all if None, or filtered by names

## Step 5: Implement Repairer (`repairer.py`)

```python
def repair(text: str, strategies: list[str] | None = None) -> RepairResult:
    """Apply repair strategies in order, try to parse after each one."""
```

Logic:
1. Try `json.loads(text)` — if it works, return immediately (no repair needed)
2. Apply each strategy in order, accumulating the text transformations
3. After ALL strategies have been applied, try `json.loads(result)`
4. If successful, return `RepairResult(repaired=True, text=result, strategies_applied=[...])`
5. If still failing, also try applying strategies one at a time with parse attempts between each
6. If all fails, return `RepairResult(repaired=False, text=text, parse_error=str(e))`

## Step 6: Implement Validator (`validator.py`)

```python
def validate(text: str, schema: dict) -> ValidationResult:
    """Parse text as JSON, validate against schema."""
```

Logic:
1. Try `json.loads(text)`
2. If parse fails, return ValidationResult with parse error
3. If parse succeeds, validate against schema using `jsonschema.validate`
4. Convert jsonschema errors to `ValidationError` objects with JSON paths
5. Return ValidationResult

## Step 7: Implement Retry Prompt Generation (`retry.py`)

```python
def retry_prompt(text: str, schema: dict, errors: list[ValidationError]) -> str:
    """Generate a correction prompt for the LLM."""
```

Generate a prompt like:
```
The JSON output you provided does not match the required schema. Please fix the following errors and return ONLY valid JSON with no additional text or markdown formatting:

Errors found:
1. At $.items[0].price: expected type 'number', got 'string'
2. At $.metadata: missing required property 'timestamp'

The expected schema requires:
- A root object with properties: items (array), metadata (object)
- Each item must have: name (string), price (number)
- Metadata must have: timestamp (string)

Return ONLY the corrected JSON.
```

Include a summary of the schema requirements (extract from schema properties/required fields). Truncate the original output if it's too long (>500 chars).

## Step 8: Implement OutputGuard Class (`guard.py`)

```python
class OutputGuard:
    def __init__(
        self,
        strategies: list[str] | None = None,
        max_repair_attempts: int = 3,
    ):
        self.strategies = strategies
        self.max_repair_attempts = max_repair_attempts

    def validate(self, text: str, schema: dict) -> ValidationResult:
        ...

    def repair(self, text: str) -> RepairResult:
        ...

    def validate_and_repair(self, text: str, schema: dict) -> ValidationResult:
        """Validate, and if invalid, attempt repair then re-validate."""
        ...

    def retry_prompt(self, text: str, schema: dict, errors: list[ValidationError]) -> str:
        ...
```

## Step 9: Implement Public API (`__init__.py`)

```python
from outputguard.guard import OutputGuard
from outputguard.models import ValidationResult, RepairResult, ValidationError

_default_guard = OutputGuard()

def validate(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate(text, schema)

def repair(text: str) -> RepairResult:
    return _default_guard.repair(text)

def validate_and_repair(text: str, schema: dict) -> ValidationResult:
    return _default_guard.validate_and_repair(text, schema)

def retry_prompt(text: str, schema: dict, errors: list[ValidationError]) -> str:
    return _default_guard.retry_prompt(text, schema, errors)
```

## Step 10: Implement CLI (`cli.py`)

Use Click:

### `outputguard validate <input>`
- `--schema / -s` — path to JSON Schema file (required)
- `--repair / -r` — attempt repair if validation fails
- `--format / -f` — text or json output
- `--quiet / -q` — exit code only
- `--output / -o` — write result to file
- Input: file path or `-` for stdin

### `outputguard repair <input>`
- `--format / -f` — text or json
- `--output / -o` — write result to file
- `--strategies` — comma-separated strategy names

### `outputguard retry-prompt <input>`
- `--schema / -s` — schema file (required)
- Prints the generated retry prompt to stdout

### `outputguard strategies`
- List all available strategies with descriptions in a table

Exit codes: 0 = valid/repaired, 1 = invalid/unrepaired, 2 = usage error.

Use `rich` for colored terminal output.

## Step 11: Create Test Fixtures

**tests/fixtures/simple_schema.json:**
```json
{
  "type": "object",
  "properties": {
    "name": {"type": "string"},
    "age": {"type": "integer"},
    "email": {"type": "string", "format": "email"}
  },
  "required": ["name", "age"]
}
```

**tests/fixtures/nested_schema.json:**
```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "price": {"type": "number"}
        },
        "required": ["name", "price"]
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "total": {"type": "integer"},
        "timestamp": {"type": "string"}
      },
      "required": ["total", "timestamp"]
    }
  },
  "required": ["items", "metadata"]
}
```

## Step 12: Write Tests

**test_strategies/test_strip_fences.py:**
- ````json\n{"a":1}\n```` → `{"a":1}`
- ````\n{"a":1}\n```` → `{"a":1}`
- No fences → unchanged
- Multiple fences → extract content from first

**test_strategies/test_extract_json.py:**
- `"Here is the JSON: {\"a\":1} Hope this helps"` → `{"a":1}`
- `"[1,2,3]"` → `[1,2,3]`
- Nested braces extracted correctly
- No JSON found → unchanged

**test_strategies/test_remove_comments.py:**
- `{"a": 1 // comment}` → `{"a": 1 }`
- `{"a": /* inline */ 1}` → `{"a":  1}`
- URLs preserved: `{"url": "http://example.com"}`

**test_strategies/test_fix_commas.py:**
- `{"a": 1, "b": 2,}` → `{"a": 1, "b": 2}`
- `[1, 2, 3,]` → `[1, 2, 3]`
- Nested trailing commas

**test_strategies/test_fix_quotes.py:**
- `{'key': 'value'}` → `{"key": "value"}`
- Mixed quotes handled

**test_strategies/test_fix_keys.py:**
- `{key: "value"}` → `{"key": "value"}`
- `{my_key: 1}` → `{"my_key": 1}`

**test_strategies/test_fix_values.py:**
- `{"a": NaN}` → `{"a": null}`
- `{"a": Infinity}` → `{"a": null}`
- `{"a": undefined}` → `{"a": null}`

**test_strategies/test_fix_closers.py:**
- `{"a": [1, 2` → `{"a": [1, 2]}`
- Already balanced → unchanged

**test_strategies/test_fix_newlines.py:**
- Literal newlines in string values → escaped

**test_validator.py:**
- Valid JSON matching schema → valid=True
- Valid JSON not matching schema → valid=False with errors
- Invalid JSON → valid=False with parse error
- Error paths are correct ($.property.nested)

**test_repairer.py:**
- Already valid JSON → no repair
- Markdown-fenced JSON → repaired
- JSON with commentary → repaired
- Multiple issues combined → repaired
- Unrepairable garbage → repaired=False

**test_retry.py:**
- Generated prompt contains error messages
- Generated prompt contains schema summary
- Long output is truncated

**test_guard.py:**
- validate_and_repair with repairable input
- validate_and_repair with unrepairable input
- Custom strategy list

**test_integration.py:**
Real-world LLM failure samples:
- `"```json\n{\"name\": \"Alice\", \"age\": 30,}\n```"` → validates after repair
- `"Sure! Here's the JSON:\n{name: 'Bob', age: 25}\nLet me know!"` → validates after repair
- `"{\"items\": [{\"name\": \"Widget\", \"price\": 9.99}], \"metadata\": {\"total\": 1, \"timestamp\": \"2024-01-01\"}}` (missing closer) → validates after repair

**test_cli.py:**
- `validate` with valid input → exit 0
- `validate` with invalid input → exit 1
- `validate --repair` with repairable input → exit 0
- `repair` command
- `strategies` command lists strategies
- `retry-prompt` produces output
- `--format json` produces valid JSON
- stdin input with `-`

## Step 13: Create Supporting Files

**.gitignore:**
```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.venv/
.pytest_cache/
.coverage
```

**LICENSE:** MIT license, copyright 2025.

## Step 14: Run Tests

```bash
uv run pytest tests/ -v --tb=short
```

Fix any failures. All tests must pass.

## Step 15: Verify CLI Works

```bash
uv run outputguard --help
uv run outputguard strategies
echo '```json\n{"name": "Alice", "age": 30}\n```' | uv run outputguard repair -
```

## Step 16: Commit

```bash
git add -A
git commit -m "feat: initial implementation of outputguard — LLM output validator & repairer

- 9 repair strategies for common LLM JSON malformations
- JSON Schema validation with detailed error paths
- Validate-and-repair pipeline
- Retry-with-feedback prompt generation
- Library API and CLI interface
- Configurable strategy pipeline
- Comprehensive test suite with real-world LLM failure samples"
```
