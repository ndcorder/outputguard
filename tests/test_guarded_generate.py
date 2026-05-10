import asyncio

import pytest

import outputguard
from outputguard import GuardedGenerationError, OutputGuard

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
    "required": ["name", "age"],
}


def test_guarded_generate_retries_until_output_validates() -> None:
    prompts: list[str] = []
    outputs = ['{"name": "Alice"}', '```json\n{"name": "Alice", "age": 30}\n```']

    def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        prompts.append(prompt)
        assert context.attempt == len(prompts) - 1
        return outputs[len(prompts) - 1]

    result = outputguard.guarded_generate(
        prompt="Return user JSON",
        schema=SIMPLE_SCHEMA,
        generate=generate,
        max_retries=2,
    )

    assert result.valid is True
    assert result.data == {"name": "Alice", "age": 30}
    assert result.text == '{"name": "Alice", "age": 30}'
    assert result.repaired is True
    assert result.strategies_applied == ["strip_fences"]
    assert len(result.attempts) == 2
    assert result.attempts[0].result.valid is False
    assert result.attempts[1].result.valid is True
    assert "age" in prompts[1]
    assert "Return ONLY" in prompts[1]


def test_guarded_generate_returns_failure_details_when_retries_exhaust() -> None:
    result = outputguard.guarded_generate(
        prompt="Return user JSON",
        schema=SIMPLE_SCHEMA,
        generate=lambda _prompt, _context: '{"name": "Alice"}',
        max_retries=1,
    )

    assert result.valid is False
    assert result.exhausted is True
    assert result.data is None
    assert any("age" in error.message for error in result.errors)
    assert len(result.attempts) == 2


def test_guarded_generate_can_disable_repair_for_strict_validation() -> None:
    result = outputguard.guarded_generate(
        prompt="Return user JSON",
        schema=SIMPLE_SCHEMA,
        generate=lambda _prompt, _context: '```json\n{"name": "Alice", "age": 30}\n```',
        max_retries=0,
        repair=False,
    )

    assert result.valid is False
    assert result.repaired is False
    assert result.strategies_applied == []
    assert result.errors[0].path == "$"


def test_guarded_generate_uses_output_guard_defaults_and_observer() -> None:
    seen_attempts: list[int] = []
    guard = OutputGuard(format="yaml")

    result = outputguard.guarded_generate(
        prompt="Return YAML",
        schema=SIMPLE_SCHEMA,
        guard=guard,
        generate=lambda _prompt, _context: "name: Alice\nage: 30\n",
        max_retries=0,
        on_attempt=lambda attempt: seen_attempts.append(attempt.attempt),
    )

    assert result.valid is True
    assert result.format == "yaml"
    assert result.data == {"name": "Alice", "age": 30}
    assert seen_attempts == [0]


def test_guarded_generate_raises_structured_error_when_requested() -> None:
    with pytest.raises(GuardedGenerationError) as exc_info:
        outputguard.guarded_generate(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=lambda _prompt, _context: '{"name": "Alice"}',
            max_retries=0,
            throw_on_failure=True,
        )

    assert exc_info.value.result.valid is False
    assert exc_info.value.result.exhausted is True


def test_async_guarded_generate_supports_async_provider() -> None:
    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        assert prompt
        assert context.attempt == 0
        return "name: Alice\nage: 30\n"

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return YAML",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            format="yaml",
            max_retries=0,
        )
    )

    assert result.valid is True
    assert result.data == {"name": "Alice", "age": 30}
    assert result.format == "yaml"
