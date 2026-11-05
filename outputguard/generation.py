from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from types import CoroutineType, GeneratorType
from typing import Any, TypeGuard, TypeVar

from outputguard._inputs import is_text, require_schema, require_text
from outputguard.configuration import attempt_limit, generation_callbacks, select_format
from outputguard.exceptions import OutputGuardError
from outputguard.guard import OutputGuard
from outputguard.models import Schema, ValidationError, ValidationResult
from outputguard.strategies import select_strategy_names

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
AsyncGenerateFn = Callable[[str, GuardedGenerateContext], Awaitable[str] | str]
AttemptObserver = Callable[[GuardedGenerateAttempt], None]
AsyncAttemptObserver = Callable[[GuardedGenerateAttempt], Awaitable[None] | None]


def _check_sync_callback(callback, name):
    if inspect.iscoroutinefunction(callback) or inspect.iscoroutinefunction(
        getattr(callback, "__call__", None)  # noqa: B004 - inspect async behavior, not callability
    ):
        raise TypeError(f"{name} is asynchronous; use guarded_generate_async")


def _close_unstarted_coroutine(value):
    if type(value) is CoroutineType and inspect.getcoroutinestate(value) == inspect.CORO_CREATED:
        value.close()


def _is_awaitable(value: object) -> TypeGuard[Awaitable[Any]]:
    actual_type = type(value)
    return issubclass(actual_type, Awaitable) or (
        actual_type is GeneratorType and inspect.isawaitable(value)
    )


def _generated_text(value: object) -> str:
    if not is_text(value):
        _close_unstarted_coroutine(value)
        raise TypeError("generate must return a string")
    return value


def guarded_generate(
    *,
    prompt: str,
    schema: Schema,
    generate: GenerateFn,
    guard: OutputGuard | None = None,
    max_retries: int | float = 2,
    format: str | None = None,
    repair: bool = True,
    include_message_history: bool = True,
    throw_on_failure: bool = False,
    on_attempt: AttemptObserver | None = None,
) -> GuardedGenerateResult:
    max_retries = attempt_limit(max_retries, "max_retries")
    generation_callbacks(generate, on_attempt)
    _check_sync_callback(generate, "generate")
    _check_sync_callback(on_attempt, "on_attempt")
    active_guard = guard if guard is not None else OutputGuard()
    data_format = select_format(format, active_guard.format)
    require_text(prompt, "prompt")
    require_schema(schema)
    if repair:
        attempt_limit(active_guard.max_repair_attempts, "max_repair_attempts")
        select_strategy_names(active_guard.strategies)
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
        raw_text = _generated_text(generate(current_prompt, context))
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
        if on_attempt is not None:
            observed = on_attempt(attempt)
            if _is_awaitable(observed):
                _close_unstarted_coroutine(observed)
                raise TypeError("on_attempt returned an awaitable; use guarded_generate_async")

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
    schema: Schema,
    generate: AsyncGenerateFn,
    guard: OutputGuard | None = None,
    max_retries: int | float = 2,
    format: str | None = None,
    repair: bool = True,
    include_message_history: bool = True,
    throw_on_failure: bool = False,
    on_attempt: AsyncAttemptObserver | None = None,
) -> GuardedGenerateResult:
    max_retries = attempt_limit(max_retries, "max_retries")
    generation_callbacks(generate, on_attempt)
    active_guard = guard if guard is not None else OutputGuard()
    data_format = select_format(format, active_guard.format)
    require_text(prompt, "prompt")
    require_schema(schema)
    if repair:
        attempt_limit(active_guard.max_repair_attempts, "max_repair_attempts")
        select_strategy_names(active_guard.strategies)
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
        generated = generate(current_prompt, context)
        raw_text = _generated_text(await generated if _is_awaitable(generated) else generated)
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
        if on_attempt is not None:
            observed = on_attempt(attempt)
            if _is_awaitable(observed):
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
