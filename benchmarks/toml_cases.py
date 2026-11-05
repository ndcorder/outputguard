"""Generate TOML documents with expected data independent of the parser."""

from __future__ import annotations

import json
import random
from pathlib import Path

from benchmarks.parsing_cases import expected_result


def toml_fixture_cases() -> list[dict]:
    fixtures = json.loads(Path(__file__).with_name("toml_cases.json").read_text())
    cases = []
    for fixture in fixtures:
        if fixture.get("js_valid") is False:
            continue  # Python preserves integers beyond JavaScript's safe range.
        case = {"name": "toml-profile-" + fixture["name"], "format": "toml", "schema": True}
        if "value_kind" in fixture:
            case.update(
                operation="validate_batch",
                texts=[fixture["text"]],
                expected={
                    "summary": {
                        "total": 1,
                        "valid": 1,
                        "invalid": 0,
                        "repaired": 0,
                        "parse_failures": 0,
                        "schema_failures": 0,
                        "success_rate": 1,
                        "strategy_counts": {},
                        "formats": {"toml": 1},
                    }
                },
            )
        else:
            case.update(
                operation="validate",
                text=fixture["text"],
                expected=expected_result(
                    fixture.get("value"),
                    valid=fixture["valid"],
                    parse_failure=not fixture["valid"],
                ),
            )
        cases.append(case)
    return cases


def generate_toml_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("toml_cases.json").read_text())
    atoms = [
        case
        for case in fixtures
        if case["valid"]
        and case.get("js_valid") is not False
        and "value_kind" not in case
        and case["text"].startswith("value = ")
        and not any(character in case["text"] for character in "\n\r#")
    ]
    malformed = [case for case in fixtures if not case["valid"]]
    cases = []
    for index in range(count):
        broken = rng.randrange(5) == 0
        if broken:
            text, data = rng.choice(malformed)["text"], None
        else:
            fixture = rng.choice(atoms)
            source, value = fixture["text"][8:], fixture["value"]["value"]
            if rng.choice([True, False]):
                year, month = rng.randrange(1, 10000), rng.randrange(1, 13)
                day = rng.randrange(1, 29)
                date = f"{year:04}-{month:02}-{day:02}"
                hour, minute, second = rng.randrange(24), rng.randrange(60), rng.randrange(60)
                short = rng.choice([True, False])
                time = f"{hour:02}:{minute:02}"
                expanded = time + f":{0 if short else second:02}"
                if not short:
                    time = expanded
                    if rng.choice([True, False]):
                        fraction = "." + "".join(
                            str(rng.randrange(10)) for _ in range(rng.randrange(1, 25))
                        )
                        time += fraction
                        expanded += fraction
                offset = rng.choice(["", "Z", "z", "+00:00", "-00:00", "+05:45", "-07:00"])
                source = date + rng.choice(["T", "t", " "]) + time + offset
                value = date + "T" + expanded + offset.upper()
            for _ in range(rng.randrange(5)):
                if rng.choice([True, False]):
                    source, value = "[" + source + ", true]", [value, True]
                else:
                    key = rng.choice(["date", "a/b", "a~b", "__proto__", "constructor", "Ω", ""])
                    source, value = "{" + json.dumps(key) + "=" + source + "}", {key: value}
            text, data = "value = " + source, {"value": value}
        valid = rng.randrange(4) != 0
        schema = rng.choice([True, {}, {"const": data}, {"enum": [data]}]) if valid else False
        if rng.choice([True, False]):
            schema = {"definitions": {"value": schema}, "$ref": "#/definitions/value"}
        cases.append(
            {
                "name": f"toml-seed-{seed}-case-{index}",
                "operation": "validate"
                if broken
                else rng.choice(["validate", "validate_and_repair"]),
                "text": text,
                "schema": schema,
                "format": rng.choice(["toml", "auto", "forced-json-off"]) if not broken else "toml",
                "expected": expected_result(data, valid=valid and not broken, parse_failure=broken),
            }
        )
    return cases
