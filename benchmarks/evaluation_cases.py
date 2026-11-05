"""Generate boolean-evaluation resource scopes with independent validity."""

import json
import random


def generate_evaluation_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for index in range(count):
        keyword = rng.choice(["if", "contains", "not", "oneOf"])
        position = rng.choice(["root", "property", "resource", "annotation"])
        value = rng.choice([None, False, 0, 42, "wrong", [], {}])
        matched = type(value) is int
        recursive = position != "annotation" and rng.randrange(4) == 0
        missing = not recursive and rng.randrange(8) == 0
        ignored_id = not recursive and not missing and rng.randrange(4) == 0
        target = {"$id": "folder/check.json", "properties": {"value": {"$ref": "leaf.json"}}}
        integer = (
            {"properties": {"value": {"type": "integer"}}} if ignored_id else {"type": "integer"}
        )
        decoy = {"properties": {"value": {"type": "string"}}} if ignored_id else {"type": "string"}
        resources = {
            "leaf": {"$id": "folder/leaf.json", **(decoy if ignored_id else integer)},
            "decoy": {"$id": "leaf.json", **(integer if ignored_id else decoy)},
        }
        if ignored_id:
            target = {"$id": "folder/ignored.json", "$ref": "leaf.json"}
        elif missing:
            del resources["leaf"]
        data = {"value": value}
        if recursive:
            target["properties"]["next"] = {"$ref": "check.json"}
            for _ in range(rng.randrange(1, 4)):
                data = {"next": data}
        if rng.choice([True, False]):
            target["$schema"] = "http://json-schema.org/draft-07/schema#"
        parent = {}
        if keyword == "if":
            parent.update({"if": target, "then": False, "else": True})
            valid = not matched
        elif keyword == "contains":
            parent["contains"] = target
            data = [data]
            valid = matched
        elif keyword == "not":
            parent["not"] = target
            valid = not matched
        else:
            alternative = rng.choice([True, {"type": "null"}])
            parent["oneOf"] = [alternative, target]
            if rng.choice([True, False]):
                parent["oneOf"].reverse()
            valid = not matched if alternative is True else matched
        if rng.choice([True, False]):
            parent["$schema"] = "http://json-schema.org/draft-07/schema#"
        if position == "annotation":
            schema = {
                "definitions": resources,
                "default": parent,
                "$ref": rng.choice(["#/default", "#%2Fdefault"]),
            }
        else:
            parent["definitions"] = resources
            if position == "property":
                schema, data = {"properties": {"payload": parent}}, {"payload": data}
            elif position == "resource":
                schema = {
                    "definitions": {"parent": {"$id": "container/parent.json", **parent}},
                    "$ref": "container/parent.json",
                }
            else:
                schema = parent
        if rng.choice([True, False]):
            schema["$id"] = rng.choice(["root.json", "https://outputguard.test/root.json"])
        expected = {"schema_error": "unresolvable"} if missing else {"valid": valid}
        cases.append(
            {
                "name": f"evaluation-seed-{seed}-case-{index}",
                "schema": schema,
                "text": json.dumps(data),
                "expected_result": expected,
            }
        )
    return cases
