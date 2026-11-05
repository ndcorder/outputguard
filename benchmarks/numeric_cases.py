"""Construct decimal multiples and nonmultiples without float arithmetic."""

import json
import random
from fractions import Fraction
from pathlib import Path


def generate_numeric_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixed = json.loads(Path(__file__).with_name("numeric_cases.json").read_text())
    cases = []
    for index in range(count):
        if index % 5 == 0:
            selected = fixed[(index // 5) % len(fixed)]
            text, divisor, matched = selected["text"], selected["divisor"], selected["valid"]
        else:
            coefficient, multiplier = rng.randrange(1, 1000000), rng.randrange(-100, 101)
            exponent = rng.randrange(-280, 281)
            matched = rng.choice([True, False])
            # Multiples share their decimal scale. For nonmultiples, one extra
            # decimal place makes the numerator 1 modulo 10 * coefficient.
            numerator = coefficient * multiplier if matched else coefficient * multiplier * 10 + 1
            text = f"{numerator}e{exponent if matched else exponent - 1}"
            divisor = float(f"{coefficient}e{exponent}")
        value = json.loads(text)
        if value == int(value) and divisor == int(divisor):
            # Whole floating-point values have an exact integer value even
            # above 2**53. Use a rational oracle rather than their display text.
            matched = (Fraction(value) / Fraction(divisor)).denominator == 1
        constraint = {"multipleOf": divisor}
        if rng.choice([True, False]):
            constraint["$schema"] = "http://json-schema.org/draft-07/schema#"
        position = rng.choice(
            ["root", "property", "items", "resource", "literal", "contains", "not", "if", "oneOf"]
        )
        wanted, data, path = matched, value, "$"
        if position == "property":
            schema, data, path = {"properties": {"value": constraint}}, {"value": value}, "$.value"
        elif position == "items":
            schema, data, path = {"items": constraint}, [value], "$[0]"
        elif position == "resource":
            schema = {
                "definitions": {"value": {"$id": "numeric.json", **constraint}},
                "$ref": "numeric.json",
            }
        elif position == "literal":
            schema = {"default": constraint, "$ref": "#%2Fdefault"}
        elif position == "contains":
            schema, data = {"contains": constraint}, [value]
        elif position == "not":
            schema, wanted = {"not": constraint}, not matched
        elif position == "if":
            schema, wanted = {"if": constraint, "then": False, "else": True}, not matched
        elif position == "oneOf":
            schema, wanted = {"oneOf": [True, constraint]}, not matched
        else:
            schema = constraint
        expected = {"valid": wanted}
        if (
            position in {"root", "property", "items", "resource", "literal"}
            and abs(value) <= 2**53 - 1
        ):
            expected.update(paths=[] if wanted else [path], values=[] if wanted else [value])
        cases.append(
            {
                "name": f"numeric-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases
