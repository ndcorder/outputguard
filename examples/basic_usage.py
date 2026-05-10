"""Basic outputguard usage — validate and repair LLM structured output."""

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

# YAML, TOML, Python literals, and forced-JSON-off outputs use the same API.
yaml_output = """```yaml
name: Alice
age: 30
hobbies:
  - reading
  - hiking
```"""
yaml_result = outputguard.validate_and_repair(yaml_output, schema, format="yaml")
print(f"\nYAML valid after repair: {yaml_result.valid}")  # True

python_output = "{'name': 'Alice', 'age': 30, 'hobbies': ['reading', 'hiking']}"
python_result = outputguard.validate_and_repair(python_output, schema, format="forced-json-off")
print(f"Forced-JSON-off valid: {python_result.valid}")  # True
