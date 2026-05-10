from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from outputguard.exceptions import OutputGuardError
from outputguard.guard import OutputGuard
from outputguard.models import ValidationError, ValidationResult

T = TypeVar("T")


@dataclass
class GuardedGenerateContext:
    attempt: int
    prompt: str
    previous_text: str | None = None
    previous_result: ValidationResult | None = None


@dataclass
class GuardedGenerateAttempt:
    attempt: int
    prompt: str
    raw_text: str
    result: ValidationResult


@dataclass
class GuardedGenerateResult:
    valid: bool
    data: Any = None
    text: str = ""
    attempts: list[GuardedGenerateAttempt] = field(default_factory=list)
    errors: list[ValidationError] = field(default_factory=list)
    repaired: bool = False
    strategies_applied: list[str] = field(default_factory=list)
    exhausted: bool = False
    format: str = "json"


class GuardedGenerationError(OutputGuardError):
    def __init__(self, message: str, result: GuardedGenerateResult):
        super().__init__(message)
        self.result = result


GenerateFn = Callable[[str, GuardedGenerateContext], str]
AsyncGenerateFn = Callable[[str, GuardedGenerateContext], Awaitable[str]]
AttemptObserver = Callable[[GuardedGenerateAttempt], None]
AsyncAttemptObserver = Callable[[GuardedGenerateAttempt], Awaitable[None]]


def guarded_generate(
    *,
    prompt: str,
    schema: dict,
    generate: GenerateFn,
    guard: OutputGuard | None = None,
    max_retries: int = 2,
    format: str | None = None,
    repair: bool = True,
    include_message_history: bool = True,
    throw_on_failure: bool = False,
    on_attempt: AttemptObserver | None = None,
) -> GuardedGenerateResult:
    active_guard = guard or OutputGuard(format=format or "json")
    data_format = format or active_guard.format
    attempts: list[GuardedGenerateAttempt] = []
    current_prompt = prompt
    previous_text: str | None = None
    previous_result: ValidationResult | None = None

    for attempt_number in range(max_retries + 1):
        context = GuardedGenerateContext(
            attempt=attempt_number,
            prompt=current_prompt,
            previous_text=previous_text,
            previous_result=previous_result,
        )
        raw_text = generate(current_prompt, context)
        result = (
            active_guard.validate_and_repair(raw_text, schema, data_format)
            if repair
            else active_guard.validate(raw_text, schema, data_format)
        )
        attempt = GuardedGenerateAttempt(
            attempt=attempt_number,
            prompt=current_prompt,
            raw_text=raw_text,
            result=result,
        )
        attempts.append(attempt)
        if on_attempt:
            on_attempt(attempt)

        if result.valid:
            return GuardedGenerateResult(
                valid=True,
                data=result.data,
                text=result.repaired_text or raw_text,
                attempts=attempts,
                repaired=any(item.result.repaired for item in attempts),
                strategies_applied=_collect_strategies(attempts),
                format=data_format,
            )

        previous_text = result.repaired_text or raw_text
        previous_result = result
        if attempt_number < max_retries:
            current_prompt = active_guard.retry_prompt(
                previous_text,
                schema,
                result.errors,
                data_format,
                include_message_history=include_message_history,
            )

    failed = GuardedGenerateResult(
        valid=False,
        data=None,
        text=previous_text or "",
        attempts=attempts,
        errors=previous_result.errors if previous_result else [],
        repaired=any(item.result.repaired for item in attempts),
        strategies_applied=_collect_strategies(attempts),
        exhausted=True,
        format=data_format,
    )
    if throw_on_failure:
        raise GuardedGenerationError(
            f"Failed to generate valid {data_format} output after {len(attempts)} attempt(s)",
            failed,
        )
    return failed


async def guarded_generate_async(
    *,
    prompt: str,
    schema: dict,
    generate: AsyncGenerateFn,
    guard: OutputGuard | None = None,
    max_retries: int = 2,
    format: str | None = None,
    repair: bool = True,
    include_message_history: bool = True,
    throw_on_failure: bool = False,
    on_attempt: AsyncAttemptObserver | None = None,
) -> GuardedGenerateResult:
    active_guard = guard or OutputGuard(format=format or "json")
    data_format = format or active_guard.format
    attempts: list[GuardedGenerateAttempt] = []
    current_prompt = prompt
    previous_text: str | None = None
    previous_result: ValidationResult | None = None

    for attempt_number in range(max_retries + 1):
        context = GuardedGenerateContext(
            attempt=attempt_number,
            prompt=current_prompt,
            previous_text=previous_text,
            previous_result=previous_result,
        )
        raw_text = await generate(current_prompt, context)
        result = (
            active_guard.validate_and_repair(raw_text, schema, data_format)
            if repair
            else active_guard.validate(raw_text, schema, data_format)
        )
        attempt = GuardedGenerateAttempt(
            attempt=attempt_number,
            prompt=current_prompt,
            raw_text=raw_text,
            result=result,
        )
        attempts.append(attempt)
        if on_attempt:
            observed = on_attempt(attempt)
            if inspect.isawaitable(observed):
                await observed

        if result.valid:
            return GuardedGenerateResult(
                valid=True,
                data=result.data,
                text=result.repaired_text or raw_text,
                attempts=attempts,
                repaired=any(item.result.repaired for item in attempts),
                strategies_applied=_collect_strategies(attempts),
                format=data_format,
            )

        previous_text = result.repaired_text or raw_text
        previous_result = result
        if attempt_number < max_retries:
            current_prompt = active_guard.retry_prompt(
                previous_text,
                schema,
                result.errors,
                data_format,
                include_message_history=include_message_history,
            )

    failed = GuardedGenerateResult(
        valid=False,
        data=None,
        text=previous_text or "",
        attempts=attempts,
        errors=previous_result.errors if previous_result else [],
        repaired=any(item.result.repaired for item in attempts),
        strategies_applied=_collect_strategies(attempts),
        exhausted=True,
        format=data_format,
    )
    if throw_on_failure:
        raise GuardedGenerationError(
            f"Failed to generate valid {data_format} output after {len(attempts)} attempt(s)",
            failed,
        )
    return failed


def _collect_strategies(attempts: list[GuardedGenerateAttempt]) -> list[str]:
    seen: dict[str, None] = {}
    for attempt in attempts:
        for strategy in attempt.result.strategies_applied:
            seen[strategy] = None
    return list(seen)
