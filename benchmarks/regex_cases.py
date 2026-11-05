"""Generate ECMAScript matches with independently known outcomes."""

import json
import random
from pathlib import Path


def _escape(value):
    return "".join("\\" + char if char in r"\^$.*+?()[]{}|" else char for char in value)


def _path(key):
    if key and key.isascii() and key.replace("$", "_").isidentifier():
        return "." + key
    return (
        "["
        + json.dumps(key, ensure_ascii=False).encode("utf-8", "backslashreplace").decode("utf-8")
        + "]"
    )


def generate_regex_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    fixtures = json.loads(Path(__file__).with_name("regex_cases.json").read_text())
    formats = [
        c
        for c in json.loads(Path(__file__).with_name("schema_formats.json").read_text())
        if c["format"] == "regex"
    ]
    cases = []
    for index in range(count):
        base = rng.choice(fixtures)
        expression, data, valid = base["pattern"], base["text"], base["valid"]
        schema = {"pattern": expression}
        if rng.randrange(3) == 0:
            prefix, suffix = (
                rng.choice(["a/b", "a~b", "Ω", "😀", "__proto__", "", ".", "$", "("])
                for _ in range(2)
            )
            digits = "".join(str(rng.randrange(10)) for _ in range(rng.randrange(1, 5)))
            expression = (
                "^"
                + _escape(prefix)
                + "(?<digits>[0-9]{"
                + str(len(digits))
                + "})"
                + _escape(suffix)
                + r"\k<digits>$"
            )
            valid = rng.choice([True, False])
            repeated = digits if valid else digits[:-1] + str((int(digits[-1]) + 1) % 10)
            data = prefix + digits + suffix + repeated
            schema = {"pattern": expression}
        locations = [] if valid else [("", data)]
        mode = rng.randrange(5)
        if mode == 0:
            base = rng.choice(formats)
            data, valid = base["value"], base["valid"]
            schema = {"format": "regex"}
            locations = [] if valid else [("", data)]
        elif mode == 4:
            schema = {
                "properties": {"__proto__": True},
                "patternProperties": {r"^even_(?<index>[0-9]+)$": {"type": "integer"}},
                "additionalProperties": {"type": "string"},
            }
            data = {"__proto__": None}
            for i in range(rng.randrange(8, 30)):
                data[f"even_{i}"] = i
                data[f"odd_{i}"] = str(i)
            valid = rng.choice([True, False])
            locations = []
            if not valid:
                key, value = rng.choice([("even_0", "wrong"), ("odd_0", 0)])
                data[key] = value
                locations = [(_path(key), value)]
        elif mode in (1, 2) and isinstance(data, str):
            key = data
            schema = {
                "patternProperties": {expression: {"type": "string"} if mode == 1 else True},
                "additionalProperties": {"type": "number"} if mode == 1 else False,
            }
            data = {key: 1}
            if mode == 1:
                valid = not valid
                locations = [] if valid else [(_path(key), 1)]
            else:
                locations = [] if valid else [("", data)]
        for _ in range(rng.randrange(4)):
            if rng.choice([True, False]):
                key = rng.choice(["entry", "__proto__", "constructor", "a/b", "Ω"])
                schema, data = {"properties": {key: schema}}, {key: data}
                locations = [(_path(key) + path, value) for path, value in locations]
            else:
                schema, data = {"items": schema}, [data, data]
                locations = [
                    (f"[{i}]" + path, value) for i in range(2) for path, value in locations
                ]
        keyword = rng.choice(["definitions", "default"])
        schema = (
            {"definitions": {"check": schema}, "$ref": "#/definitions/check"}
            if keyword == "definitions"
            else {"default": schema, "$ref": "#/default"}
        )
        locations.sort(key=lambda pair: pair[0])
        cases.append(
            {
                "name": f"regex-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": {
                    "valid": valid,
                    "paths": ["$" + p for p, _ in locations],
                    "values": [v for _, v in locations],
                },
            }
        )
    return cases
