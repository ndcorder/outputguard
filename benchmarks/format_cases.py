"""Compose format assertions around explicit and independently generated data."""

from __future__ import annotations

import calendar
import json
import random
from pathlib import Path


def generate_format_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("schema_formats.json").read_text())
    cases = []
    for index in range(count):
        base = rng.choice(fixtures)
        name, data, valid = base["format"], base["value"], base["valid"]
        kind = rng.randrange(5)
        if kind == 0:
            name = "date"
            year, month = rng.randrange(1, 10000), rng.randrange(1, 13)
            day = rng.randrange(0, 34)
            data = f"{year:04}-{month:02}-{day:02}"
            valid = 1 <= day <= calendar.monthrange(year, month)[1]
        elif kind == 1:
            name = "email"
            user = "user" + str(rng.randrange(100000))
            data = user + "@example.com"
            valid = rng.choice([True, False])
            if not valid:
                data = rng.choice([user + "..x@example.com", user + "@-example.com", data + "\n"])
        elif kind == 2:
            name = "ipv4"
            parts = [str(rng.randrange(256)) for _ in range(4)]
            valid = rng.choice([True, False])
            if not valid:
                parts[rng.randrange(4)] = rng.choice(["256", "01", "-1", "１２"])
            data = ".".join(parts)
        elif kind == 3:
            name = "json-pointer"
            key = rng.choice(["a/b", "a~b", "__proto__", "Ω", "", "0", "a\nb"])
            data = "/" + key.replace("~", "~0").replace("/", "~1")
            valid = rng.choice([True, False])
            if not valid:
                data += "~2"
        unsafe = isinstance(data, int) and not isinstance(data, bool) and abs(data) > 2**53 - 1
        schema = {"format": name}
        locations = [("", data)] if not valid else []
        for _ in range(rng.randrange(5)):
            if rng.choice([True, False]):
                key, path = rng.choice(
                    [
                        ("entry", ".entry"),
                        ("__proto__", ".__proto__"),
                        ("constructor", ".constructor"),
                        ("a/b", '["a/b"]'),
                        ("Ω", '["Ω"]'),
                    ]
                )
                schema, data = {"properties": {key: schema}}, {key: data}
                locations = [(path + suffix, value) for suffix, value in locations]
            else:
                schema, data = {"items": schema}, [data, data]
                locations = [
                    (f"[{i}]" + suffix, value) for i in range(2) for suffix, value in locations
                ]
        if rng.choice([True, False]):
            schema = {"definitions": {"target": schema}, "$ref": "#/definitions/target"}
        else:
            schema = {"default": schema, "$ref": "#/default"}
        # JSON serialization cannot transport an exact unsafe JS integer back
        # into Python. These cases check validity; the explicit API corpus also
        # checks their parse/schema classification using batch summaries.
        expected = {"valid": valid}
        if not unsafe:
            locations.sort(key=lambda pair: pair[0])
            expected.update(
                paths=["$" + path for path, _ in locations], values=[v for _, v in locations]
            )
        cases.append(
            {
                "name": f"formats-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases
