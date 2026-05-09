"""Basic outputguard usage — validate and repair LLM JSON output."""

import outputguard

# Define your expected schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
        "hobbies": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["name", "age"],
}

# Typical LLM output with common issues:
# - Wrapped in markdown code fences
# - Trailing comma
# - Single quotes
llm_output = """```json
{'name': 'Alice', 'age': 30, 'hobbies': ['reading', 'hiking',]}
```"""

# Option 1: Validate only (will fail because of formatting issues)
result = outputguard.validate(llm_output, schema)
print(f"Valid without repair: {result.valid}")  # False

# Option 2: Validate and auto-repair (handles all the issues)
result = outputguard.validate_and_repair(llm_output, schema)
print(f"Valid after repair: {result.valid}")  # True
print(f"Repaired: {result.repaired}")  # True
print(f"Strategies used: {result.strategies_applied}")
print(f"Clean data: {result.data}")
# {'name': 'Alice', 'age': 30, 'hobbies': ['reading', 'hiking']}

# Option 3: Repair without schema validation
repair_result = outputguard.repair(llm_output)
print(f"\nRepair-only result: {repair_result.text}")
