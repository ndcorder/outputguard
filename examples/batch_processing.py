"""Batch processing — validate multiple LLM outputs with built-in statistics."""

import json

import outputguard

schema = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "score": {"type": "number"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "score"],
}

# Simulate a batch of LLM outputs with various issues
batch = [
    '{"category": "tech", "score": 0.9, "tags": ["ai", "ml"]}',  # Valid
    '```json\n{"category": "science", "score": 0.85}\n```',  # Fenced
    "{category: 'sports', score: 0.7}",  # Unquoted keys + single quotes
    '{"category": "music", "score": 0.6,}',  # Trailing comma
    'Here is the result: {"category": "art", "score": 0.5}',  # Commentary
    "not json at all",  # Unrepairable
    '{"category": "food", "score": NaN}',  # NaN value
    '{"category": "travel", "score": 0.8, "tags": ["beach",]}',  # Trailing comma in array
]


print("Processing batch of LLM outputs...")
print()
batch_result = outputguard.validate_batch(batch, schema, repair=True)

for result in batch_result.results:
    number = result.index + 1
    if result.valid and result.repaired:
        print(f"  [{number}] Repaired ({', '.join(result.strategies_applied)})")
    elif result.valid:
        print(f"  [{number}] Valid")
    else:
        errors = "; ".join(error.message[:50] for error in result.errors)
        print(f"  [{number}] Failed: {errors}")

print("\n--- Batch Summary ---")
summary = batch_result.summary
print(f"Total:        {summary.total}")
print(f"Valid:        {summary.valid}")
print(f"Repaired:     {summary.repaired}")
print(f"Failed:       {summary.invalid}")
print(f"Success rate: {summary.success_rate:.0%}")

if summary.strategy_counts:
    print("\nMost-used strategies:")
    for strategy, count in sorted(
        summary.strategy_counts.items(), key=lambda item: item[1], reverse=True
    ):
        print(f"  {strategy}: {count}")

print("\nValid results:")
for result in batch_result.results:
    if result.valid:
        print(f"  {json.dumps(result.data)}")
