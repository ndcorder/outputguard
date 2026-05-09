"""Test outputguard against real LLM model outputs.

These tests run against saved fixtures from actual LLM API calls.
To regenerate fixtures: python -m tests.real_model_runner

To run live tests against OpenRouter (requires API key):
    pytest tests/test_real_models.py -k TestLiveModels -v
"""

import json
import os
import urllib.request
import urllib.error

import pytest
from pathlib import Path

from outputguard import repair, validate_and_repair

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "real_outputs"

# Schemas matching the scenarios in real_model_runner.py
SCHEMAS = {
    "simple_object": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "email": {"type": "string"},
        },
        "required": ["name", "age", "email"],
    },
    "nested_array": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "price": {"type": "number"}},
                    "required": ["name", "price"],
                },
            },
            "metadata": {
                "type": "object",
                "properties": {"currency": {"type": "string"}},
            },
        },
        "required": ["items", "metadata"],
    },
    "enum_values": {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "confidence": {"type": "number"},
            "keywords": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["text", "sentiment", "confidence"],
    },
    "boolean_fields": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "completed": {"type": "boolean"},
            "priority": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "completed", "priority"],
    },
    "large_response": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "username": {"type": "string"},
                "active": {"type": "boolean"},
                "score": {"type": "number"},
            },
            "required": ["id", "username", "active", "score"],
        },
    },
}


def get_fixture_files() -> list[Path]:
    """Discover all saved fixture files."""
    if not FIXTURES_DIR.exists():
        return []
    return sorted(FIXTURES_DIR.glob("*.txt"))


def parse_fixture_name(path: Path) -> tuple[str, str]:
    """Extract model and scenario from fixture filename."""
    stem = path.stem  # e.g. "openai__gpt-4o-mini__simple_object"
    parts = stem.split("__")
    if len(parts) >= 3:
        model = f"{parts[0]}/{parts[1]}"
        scenario = "__".join(parts[2:])
        return model, scenario
    return stem, "unknown"


fixture_files = get_fixture_files()


@pytest.mark.skipif(
    not fixture_files, reason="No real output fixtures found. Run: python -m tests.real_model_runner"
)
class TestRealModelFixtures:
    """Test outputguard against saved real LLM outputs."""

    @pytest.mark.parametrize(
        "fixture_path", fixture_files, ids=[f.stem for f in fixture_files]
    )
    def test_repair_produces_valid_json(self, fixture_path: Path):
        """Every real LLM output should be repairable to valid JSON."""
        raw = fixture_path.read_text()
        result = repair(raw)
        if result.parse_error:
            pytest.fail(
                f"Could not repair output from {fixture_path.stem}: "
                f"{result.parse_error}\nRaw: {raw[:200]}"
            )
        json.loads(result.text)  # Must not raise

    # Model outputs that returned a completely wrong structure (not an outputguard bug)
    KNOWN_MODEL_MISMATCHES = {
        "google__gemini-2.5-flash__nested_array",  # returns bare array instead of {items, metadata}
    }

    @pytest.mark.parametrize(
        "fixture_path", fixture_files, ids=[f.stem for f in fixture_files]
    )
    def test_validate_and_repair_against_schema(self, fixture_path: Path):
        """Every real LLM output should validate against its intended schema after repair."""
        raw = fixture_path.read_text()
        model, scenario = parse_fixture_name(fixture_path)

        if fixture_path.stem in self.KNOWN_MODEL_MISMATCHES:
            pytest.xfail("Model returned wrong structure (not an outputguard bug)")

        schema = SCHEMAS.get(scenario)
        if schema is None:
            pytest.skip(f"No schema for scenario: {scenario}")

        result = validate_and_repair(raw, schema)
        if not result.valid:
            errors = "; ".join(f"{e.path}: {e.message}" for e in result.errors[:3])
            pytest.fail(
                f"Failed for {model} / {scenario}\n"
                f"Errors: {errors}\n"
                f"Raw output: {raw[:300]}"
            )


# -- Live tests (call OpenRouter directly) -------------------------------------------

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

LIVE_MODELS = [
    "openai/gpt-5-mini",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-2.5-flash",
    "mistralai/mistral-medium-3-5",
    "deepseek/deepseek-v3.2",
    "qwen/qwen3.6-flash",
    "x-ai/grok-4.1-fast",
]


def call_model(model: str, prompt: str) -> str:
    """Call OpenRouter API and return the raw text response."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ndcorder/outputguard",
            "X-Title": "outputguard-test",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


live = pytest.mark.skipif(not OPENROUTER_API_KEY, reason="OPENROUTER_API_KEY not set")


@live
class TestLiveModels:
    """Call real LLM models via OpenRouter and verify outputguard handles their output.

    Run with: pytest tests/test_real_models.py -k TestLiveModels -v
    """

    @pytest.mark.parametrize("model", LIVE_MODELS)
    def test_simple_object(self, model: str):
        prompt = (
            "Return ONLY valid JSON. No markdown, no explanation.\n\n"
            "Return a JSON object with fields: name (string), age (integer), email (string)."
        )
        raw = call_model(model, prompt)
        schema = SCHEMAS["simple_object"]
        result = validate_and_repair(raw, schema)
        assert result.valid, f"{model} output not repairable: {raw[:200]}"

    @pytest.mark.parametrize("model", LIVE_MODELS)
    def test_nested_with_array(self, model: str):
        prompt = (
            "Return ONLY valid JSON. No markdown.\n\n"
            "Return a JSON object with: items (array of objects with name and price), "
            "metadata (object with total count and currency). Include 3 items."
        )
        raw = call_model(model, prompt)
        schema = SCHEMAS["nested_array"]
        result = validate_and_repair(raw, schema)
        assert result.valid, f"{model} output not repairable: {raw[:200]}"

    @pytest.mark.parametrize("model", LIVE_MODELS)
    def test_booleans_and_enums(self, model: str):
        prompt = (
            "Return ONLY valid JSON.\n\n"
            "Return: title (string), completed (boolean, false), "
            "priority (integer 1-5), tags (array of strings)."
        )
        raw = call_model(model, prompt)
        schema = SCHEMAS["boolean_fields"]
        result = validate_and_repair(raw, schema)
        assert result.valid, f"{model} output not repairable: {raw[:200]}"

    @pytest.mark.parametrize("model", LIVE_MODELS)
    def test_large_array_response(self, model: str):
        prompt = (
            "Return ONLY valid JSON.\n\n"
            "Return a JSON array of 5 user objects. Each has: "
            "id (integer), username (string), active (boolean), score (number)."
        )
        raw = call_model(model, prompt)
        schema = SCHEMAS["large_response"]
        result = validate_and_repair(raw, schema)
        assert result.valid, f"{model} output not repairable: {raw[:200]}"
