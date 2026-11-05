"""Validate decimal multiples without binary floating-point division."""

import math
from decimal import Decimal
from functools import lru_cache

import jsonschema

_native_multiple_of = jsonschema.Draft7Validator.VALIDATORS["multipleOf"]


@lru_cache(maxsize=128)
def _divisor_ratio(divisor):
    # Conversion and integer arithmetic do not depend on Decimal's context
    # precision. The bounded cache retains numbers, never schema documents.
    return _number_ratio(divisor)


def _number_ratio(value):
    if type(value) is int or value.is_integer():
        return int(value), 1
    return Decimal(str(value)).as_integer_ratio()


def _is_multiple(instance, divisor):
    if type(instance) is int and type(divisor) is int:
        return instance % divisor == 0
    if isinstance(instance, float) and not math.isfinite(instance):
        return False
    numerator, denominator = _number_ratio(instance)
    divisor_numerator, divisor_denominator = _divisor_ratio(divisor)
    return (numerator * divisor_denominator) % (denominator * divisor_numerator) == 0


def multiple_of(validator, divisor, instance, schema):
    if not validator.is_type(instance, "number"):
        return
    if (
        type(instance) not in (int, float)
        or type(divisor) not in (int, float)
        or divisor <= 0
        or isinstance(divisor, float)
        and not math.isfinite(divisor)
    ):
        # Preserve native handling for invalid schemas and non-JSON numeric
        # extensions such as Decimal or Fraction supplied directly by callers.
        yield from _native_multiple_of(validator, divisor, instance, schema)
        return
    if not _is_multiple(instance, divisor):
        yield jsonschema.ValidationError(f"{instance!r} is not a multiple of {divisor}")
