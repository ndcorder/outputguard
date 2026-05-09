"""Retry loop pattern — send correction prompts back to the LLM."""

import json

import outputguard

schema = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["summary", "sentiment", "confidence"],
}

# Simulate LLM responses (in real code, this calls your LLM API)
mock_responses = [
    # First attempt: missing required field + wrong type
    '{"summary": "Great product!", "sentiment": "positive"}',
    # Second attempt: all correct after receiving correction prompt
    '{"summary": "Great product!", "sentiment": "positive", "confidence": 0.95}',
]


def call_llm(prompt: str, response_idx: list[int]) -> str:
    """Mock LLM call — in real code, use your preferred LLM SDK."""
    idx = response_idx[0]
    response_idx[0] += 1
    return mock_responses[idx]


def get_structured_output(
    initial_prompt: str,
    schema: dict,
    max_retries: int = 3,
) -> dict:
    """Get validated structured output from an LLM with automatic retries."""
    response_idx = [0]
    prompt = initial_prompt

    for attempt in range(max_retries + 1):
        # Get LLM response
        raw_output = call_llm(prompt, response_idx)
        print(f"Attempt {attempt + 1}: {raw_output[:80]}...")

        # Validate and try to repair
        result = outputguard.validate_and_repair(raw_output, schema)

        if result.valid:
            if result.repaired:
                print(f"  ✓ Valid after repair (strategies: {result.strategies_applied})")
            else:
                print("  ✓ Valid")
            return result.data

        # Generate a correction prompt and retry
        prompt = outputguard.retry_prompt(raw_output, schema, result.errors)
        print(f"  ✗ Invalid — sending correction prompt ({len(result.errors)} errors)")

    raise RuntimeError(f"Failed to get valid output after {max_retries + 1} attempts")


# Run the example
data = get_structured_output(
    "Analyze the sentiment of: 'This product is amazing!'",
    schema,
)
print(f"\nFinal result: {json.dumps(data, indent=2)}")
