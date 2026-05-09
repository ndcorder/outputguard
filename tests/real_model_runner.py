#!/usr/bin/env python3
"""Call real LLM models via OpenRouter, save outputs as test fixtures.

Usage: python -m tests.real_model_runner
Requires: OPENROUTER_API_KEY environment variable
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from outputguard import validate_and_repair

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    # Latest gen (2025-2026)
    "openai/gpt-5-mini",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-2.5-flash",
    "mistralai/mistral-medium-3-5",
    "deepseek/deepseek-v3.2",
    "qwen/qwen3.6-flash",
    "x-ai/grok-4.1-fast",
    # Previous gen (keep for coverage)
    "openai/gpt-4.1-mini",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat-v3.1",
    "qwen/qwen3-8b",
]

SCENARIOS = [
    {
        "name": "simple_object",
        "prompt": "Return a JSON object with fields: name (string), age (integer), email (string). Use realistic values.",
        "schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["name", "age", "email"],
        },
    },
    {
        "name": "nested_array",
        "prompt": "Return a JSON object with: items (array of objects with name and price), metadata (object with total count and currency). Include 3 items.",
        "schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "price": {"type": "number"},
                        },
                        "required": ["name", "price"],
                    },
                },
                "metadata": {
                    "type": "object",
                    "properties": {
                        "currency": {"type": "string"},
                    },
                },
            },
            "required": ["items", "metadata"],
        },
    },
    {
        "name": "enum_values",
        "prompt": "Return a JSON object analyzing the sentiment of 'I love sunny days'. Fields: text (the input), sentiment (one of: positive, negative, neutral), confidence (number 0-1), keywords (array of strings).",
        "schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
                "confidence": {"type": "number"},
                "keywords": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text", "sentiment", "confidence"],
        },
    },
    {
        "name": "boolean_fields",
        "prompt": "Return a JSON object describing a task: title (string), completed (boolean), priority (integer 1-5), tags (array of strings). Make completed false.",
        "schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "completed": {"type": "boolean"},
                "priority": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "completed", "priority"],
        },
    },
    {
        "name": "large_response",
        "prompt": "Return a JSON array of 10 user objects. Each has: id (integer), username (string), active (boolean), score (number). Make the data varied and realistic.",
        "schema": {
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
    },
]


def call_openrouter(model: str, prompt: str) -> str:
    """Call OpenRouter API and return the raw text response."""
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": prompt},
        ],
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

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
        return f"ERROR: {e}"


def main():
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    output_dir = Path(__file__).parent / "fixtures" / "real_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(MODELS) * len(SCENARIOS)
    current = 0

    for model in MODELS:
        model_slug = model.replace("/", "__")
        for scenario in SCENARIOS:
            current += 1
            name = f"{model_slug}__{scenario['name']}"
            print(f"[{current}/{total}] {model} / {scenario['name']}...", end=" ", flush=True)

            system_note = "Return ONLY valid JSON. No markdown, no explanation."
            full_prompt = f"{system_note}\n\n{scenario['prompt']}"

            raw = call_openrouter(model, full_prompt)

            if raw.startswith("ERROR:"):
                print(f"SKIP ({raw})")
                continue

            # Save raw output
            output_file = output_dir / f"{name}.txt"
            output_file.write_text(raw)

            # Test with outputguard
            result = validate_and_repair(raw, scenario["schema"])

            status = (
                "VALID"
                if result.valid and not result.repaired
                else f"REPAIRED ({', '.join(result.strategies_applied)})"
                if result.valid
                else "FAILED"
            )
            print(status)

            results.append({
                "model": model,
                "scenario": scenario["name"],
                "raw_length": len(raw),
                "valid_immediately": result.valid and not result.repaired,
                "repaired": result.valid and result.repaired,
                "failed": not result.valid,
                "strategies": result.strategies_applied if result.repaired else [],
            })

    # Summary
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(results)} tests")
    valid = sum(1 for r in results if r["valid_immediately"])
    repaired = sum(1 for r in results if r["repaired"])
    failed = sum(1 for r in results if r["failed"])
    print(f"  Valid immediately: {valid}")
    print(f"  Repaired:          {repaired}")
    print(f"  Failed:            {failed}")
    print(f"  Success rate:      {(valid + repaired) / max(len(results), 1):.0%}")

    if repaired > 0:
        from collections import Counter

        strategies: Counter[str] = Counter()
        for r in results:
            for s in r["strategies"]:
                strategies[s] += 1
        print("\nMost-used strategies:")
        for s, c in strategies.most_common():
            print(f"  {s}: {c}")

    # Save summary
    summary_file = output_dir / "summary.json"
    summary_file.write_text(
        json.dumps(
            {
                "timestamp": datetime.now().isoformat(),
                "models": MODELS,
                "results": results,
            },
            indent=2,
        )
    )
    print(f"\nResults saved to {summary_file}")


if __name__ == "__main__":
    main()
