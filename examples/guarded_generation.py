"""Provider-agnostic guarded generation example."""

import outputguard

schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


class DemoLLM:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            return '{"name": "Alice"}'
        return '```json\n{"name": "Alice", "age": 30}\n```'


llm = DemoLLM()
result = outputguard.guarded_generate(
    prompt="Return a user object as JSON.",
    schema=schema,
    generate=lambda prompt, _context: llm.generate(prompt),
    max_retries=2,
)

if result.valid:
    print(result.data)
    print(f"attempts: {len(result.attempts)}")
    print(f"strategies: {result.strategies_applied}")
else:
    print(result.errors)
