"""Batch processing — validate multiple LLM outputs with statistics."""

import json
from collections import Counter
from dataclasses import dataclass

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


@dataclass
class BatchStats:
    total: int = 0
    valid_immediately: int = 0
    repaired: int = 0
    failed: int = 0
    strategies_used: Counter = None

    def __post_init__(self):
        if self.strategies_used is None:
            self.strategies_used = Counter()


def process_batch(outputs: list[str], schema: dict) -> tuple[list[dict], BatchStats]:
    """Process a batch of LLM outputs, collecting valid results and stats."""
    stats = BatchStats()
    results = []

    for i, text in enumerate(outputs):
        stats.total += 1
        result = outputguard.validate_and_repair(text, schema)

        if result.valid:
            results.append(result.data)
            if result.repaired:
                stats.repaired += 1
                for strategy in result.strategies_applied:
                    stats.strategies_used[strategy] += 1
                print(f"  [{i + 1}] Repaired ({', '.join(result.strategies_applied)})")
            else:
                stats.valid_immediately += 1
                print(f"  [{i + 1}] Valid")
        else:
            stats.failed += 1
            errors = "; ".join(e.message[:50] for e in result.errors)
            print(f"  [{i + 1}] Failed: {errors}")

    return results, stats


print("Processing batch of LLM outputs...")
print()
results, stats = process_batch(batch, schema)

print("\n--- Batch Summary ---")
print(f"Total:             {stats.total}")
print(f"Valid immediately:  {stats.valid_immediately}")
print(f"Repaired:          {stats.repaired}")
print(f"Failed:            {stats.failed}")
print(f"Success rate:      {(stats.valid_immediately + stats.repaired) / stats.total:.0%}")

if stats.strategies_used:
    print("\nMost-used strategies:")
    for strategy, count in stats.strategies_used.most_common():
        print(f"  {strategy}: {count}")

print("\nValid results:")
for r in results:
    print(f"  {json.dumps(r)}")
