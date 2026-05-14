"""Tests targeting uncovered async paths in outputguard/generation.py (lines 181-183, 196-223)."""

import asyncio

import pytest

import outputguard
from outputguard import GuardedGenerationError

SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
    "required": ["name", "age"],
}


def test_async_retry_and_success_on_second_attempt() -> None:
    """L196-207: async retry loop generates retry prompt, second attempt succeeds."""
    outputs = ['{"name": "Alice"}', '{"name": "Alice", "age": 30}']
    call_count = 0

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        nonlocal call_count
        idx = call_count
        call_count += 1
        return outputs[idx]

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=2,
        )
    )

    assert result.valid is True
    assert result.data == {"name": "Alice", "age": 30}
    assert len(result.attempts) == 2
    assert result.attempts[0].result.valid is False
    assert result.attempts[1].result.valid is True


def test_async_exhaustion_returns_failed_result() -> None:
    """L209-219: all retries exhausted, returns failed GuardedGenerateResult."""

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        return '{"name": "Alice"}'

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=1,
        )
    )

    assert result.valid is False
    assert result.exhausted is True
    assert result.data is None
    assert any("age" in e.message for e in result.errors)
    assert len(result.attempts) == 2


def test_async_throw_on_failure_raises_error() -> None:
    """L221-223: throw_on_failure raises GuardedGenerationError."""

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        return '{"name": "Alice"}'

    with pytest.raises(GuardedGenerationError) as exc_info:
        asyncio.run(
            outputguard.guarded_generate_async(
                prompt="Return user JSON",
                schema=SIMPLE_SCHEMA,
                generate=generate,
                max_retries=0,
                throw_on_failure=True,
            )
        )

    assert exc_info.value.result.valid is False
    assert exc_info.value.result.exhausted is True


def test_async_awaitable_on_attempt_observer() -> None:
    """L181-183: async on_attempt callback is awaited."""
    seen_attempts: list[int] = []

    async def on_attempt(attempt: outputguard.GuardedGenerateAttempt) -> None:
        seen_attempts.append(attempt.attempt)

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        return '{"name": "Alice", "age": 30}'

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=0,
            on_attempt=on_attempt,
        )
    )

    assert result.valid is True
    assert seen_attempts == [0]


def test_async_with_repair_disabled() -> None:
    """Async path with repair=False only validates, no repair strategies."""

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        return '```json\n{"name": "Alice", "age": 30}\n```'

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=0,
            repair=False,
        )
    )

    assert result.valid is False
    assert result.repaired is False
    assert result.strategies_applied == []


def test_async_awaitable_observer_across_retries() -> None:
    """L181-183 + L196-207: async observer fires on each attempt including retries."""
    seen_attempts: list[int] = []
    outputs = ['{"name": "Alice"}', '{"name": "Alice", "age": 30}']
    call_count = 0

    async def on_attempt(attempt: outputguard.GuardedGenerateAttempt) -> None:
        seen_attempts.append(attempt.attempt)

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        nonlocal call_count
        idx = call_count
        call_count += 1
        return outputs[idx]

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=1,
            on_attempt=on_attempt,
        )
    )

    assert result.valid is True
    assert seen_attempts == [0, 1]
    assert len(result.attempts) == 2


def test_async_exhaustion_with_awaitable_observer() -> None:
    """L181-183 + L209-223: async observer fires, then exhaustion path."""
    seen_attempts: list[int] = []

    async def on_attempt(attempt: outputguard.GuardedGenerateAttempt) -> None:
        seen_attempts.append(attempt.attempt)

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        return '{"name": "Alice"}'

    result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=1,
            on_attempt=on_attempt,
        )
    )

    assert result.valid is False
    assert result.exhausted is True
    assert seen_attempts == [0, 1]


def test_async_omit_message_history_from_retry_prompt() -> None:
    """Async path with include_message_history=False omits original output."""
    prompts: list[str] = []

    async def generate(prompt: str, context: outputguard.GuardedGenerateContext) -> str:
        prompts.append(prompt)
        return '{"name": "Sensitive"}'

    asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return user JSON",
            schema=SIMPLE_SCHEMA,
            generate=generate,
            max_retries=1,
            include_message_history=False,
        )
    )

    assert len(prompts) == 2
    assert "age" in prompts[1]
    assert "Original output:" not in prompts[1]
    assert "Sensitive" not in prompts[1]
