"""Custom pipeline configuration — pick strategies for your use case."""

import outputguard
from outputguard import OutputGuard

# Use case 1: Strict mode — only fix formatting, not content
# Good when you want minimal intervention
strict_guard = OutputGuard(
    strategies=["strip_fences", "fix_commas"],
    max_repair_attempts=1,
)

schema = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["answer", "score"],
}

# This will be repaired (just formatting)
fenced = '```json\n{"answer": "42", "score": 0.95,}\n```'
result = strict_guard.validate_and_repair(fenced, schema)
print(f"Strict mode: valid={result.valid}, strategies={result.strategies_applied}")

# This will NOT be repaired (unquoted keys need fix_keys, which we excluded)
unquoted = '{answer: "42", score: 0.95}'
result = strict_guard.validate_and_repair(unquoted, schema)
print(f"Strict mode won't fix unquoted keys: valid={result.valid}")


# Use case 2: Aggressive mode — try everything, multiple attempts
aggressive_guard = OutputGuard(
    strategies=None,  # All strategies
    max_repair_attempts=5,
)

messy = """Sure! Here's the JSON:
{name: 'Bob', age: 30, active: True, score: NaN,}
Let me know if you need anything else!"""

schema2 = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "active": {"type": "boolean"},
        "score": {"type": "null"},
    },
    "required": ["name", "age"],
}

result = aggressive_guard.validate_and_repair(messy, schema2)
print(f"\nAggressive mode: valid={result.valid}")
print(f"Strategies: {result.strategies_applied}")
print(f"Data: {result.data}")


# Use case 3: Repair-only (no schema)
# Useful when you just need parseable JSON
guard = OutputGuard()
broken = "{'items': [1, 2, 3,], 'count': undefined}"
repair_result = guard.repair(broken)
print(f"\nRepair-only: {repair_result.text}")
print(f"Strategies: {repair_result.strategies_applied}")
