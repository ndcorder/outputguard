import asyncio
import json

import pytest
from click.testing import CliRunner

import outputguard
from outputguard.cli import cli

FALSE_CASES = [
    ({"properties": {"blocked": False}}, {"blocked": 1}, "$.blocked", "$.properties.blocked", 1),
    ({"properties": {"a/b": False}}, {"a/b": 1}, '$["a/b"]', '$.properties["a/b"]', 1),
    (
        {"properties": {"__proto__": False}},
        {"__proto__": 1},
        "$.__proto__",
        "$.properties.__proto__",
        1,
    ),
    ({"items": False}, [1], "$[0]", "$.items", 1),
    ({"items": [True, False]}, [0, 1], "$[1]", "$.items[1]", 1),
    ({"patternProperties": {"^x$": False}}, {"x": 1}, "$.x", '$.patternProperties["^x$"]', 1),
    (
        {"properties": {"child": {"properties": {"blocked": False}}}},
        {"child": {"blocked": 1}},
        "$.child.blocked",
        "$.properties.child.properties.blocked",
        1,
    ),
    ({"allOf": [False]}, 1, "$", "$.allOf[0]", 1),
    ({"if": True, "then": False}, 1, "$", "$.then", 1),
    ({"if": False, "else": False}, 1, "$", "$.else", 1),
    ({"dependencies": {"flag": False}}, {"flag": True}, "$", "$.dependencies.flag", {"flag": True}),
    (
        {"$schema": "http://json-schema.org/draft-07/schema#", "properties": {"blocked": False}},
        {"blocked": 1},
        "$.blocked",
        "$.properties.blocked",
        1,
    ),
    (
        {
            "definitions": {"closed": {"properties": {"blocked": False}}},
            "$ref": "#/definitions/closed",
        },
        {"blocked": 1},
        "$.blocked",
        "$.properties.blocked",
        1,
    ),
]


@pytest.mark.parametrize("schema,data,path,schema_path,value", FALSE_CASES)
def test_false_subschema_errors_keep_locations(schema, data, path, schema_path, value):
    before = json.dumps(schema)
    result = outputguard.validate(json.dumps(data), schema)
    assert not result.valid
    assert result.parse_error is None
    assert result.errors[0].path == path
    assert result.errors[0].schema_path == schema_path
    assert result.errors[0].value == value
    assert result.errors[0].message.startswith("False schema does not allow")
    assert json.dumps(schema) == before


@pytest.mark.parametrize("schema", [True, False])
def test_boolean_root_schemas_preserve_parse_and_schema_failures(schema):
    result = outputguard.validate("null", schema)
    assert result.valid is schema
    assert result.parse_error is None
    assert not outputguard.validate("not json", schema).valid
    if schema:
        assert outputguard.parse("null", schema) is None
    else:
        with pytest.raises(outputguard.SchemaValidationError) as exc:
            outputguard.parse("null", schema)
        assert exc.value.schema is False


@pytest.mark.parametrize("schema", [True, False])
def test_boolean_roots_work_with_repairs_and_batch_summaries(schema):
    result = outputguard.validate_and_repair("```json\nnull\n```", schema)
    assert result.valid is schema
    assert result.repaired
    batch = outputguard.validate_batch(["null", "not json"], schema)
    assert batch.summary.valid == int(schema)
    assert batch.summary.parse_failures == 1
    assert batch.summary.schema_failures == int(not schema)


@pytest.mark.parametrize(
    "schema",
    [
        True,
        False,
        {"properties": {"anything": True, "blocked": False}},
        {"type": "array", "items": False},
        {"type": "array", "items": [True, False]},
    ],
)
def test_retry_prompts_support_boolean_schema_nodes(schema):
    prompt = outputguard.retry_prompt("{}", schema, [], include_message_history=False)
    assert "The expected schema requires:" in prompt
    if schema is False:
        assert "No value is allowed" in prompt
    elif schema is True:
        assert "Any parsed value is allowed" in prompt
    else:
        assert "forbidden" in prompt or "must be empty" in prompt


@pytest.mark.parametrize("async_mode", [False, True])
def test_generation_recovers_from_a_forbidden_property(async_mode):
    schema = {"properties": {"blocked": False}}

    def generate(prompt, context):
        if context.attempt:
            assert "$.blocked" in prompt
            assert "forbidden" in prompt
        return '{"blocked":1}' if context.attempt == 0 else "{}"

    async def async_generate(prompt, context):
        return generate(prompt, context)

    if async_mode:
        result = asyncio.run(
            outputguard.guarded_generate_async(
                prompt="Return JSON", schema=schema, generate=async_generate
            )
        )
    else:
        result = outputguard.guarded_generate(
            prompt="Return JSON", schema=schema, generate=generate
        )
    assert result.valid
    assert len(result.attempts) == 2


@pytest.mark.parametrize("async_mode", [False, True])
def test_generation_with_false_root_exhausts_normally(async_mode):
    async def generate_async(prompt, context):
        return "null"

    options = dict(prompt="Return JSON", schema=False, max_retries=1)
    if async_mode:
        result = asyncio.run(outputguard.guarded_generate_async(generate=generate_async, **options))
    else:
        result = outputguard.guarded_generate(generate=lambda _p, _c: "null", **options)
    assert not result.valid
    assert result.exhausted
    assert len(result.attempts) == 2


def test_false_data_and_native_keyword_semantics_are_preserved():
    schema = {
        "const": {"allowed": False, "properties": {"literal": False}},
        "default": False,
        "examples": [False],
    }
    assert outputguard.validate(json.dumps(schema["const"]), schema).valid
    additional = outputguard.validate('{"extra":1}', {"additionalProperties": False})
    assert additional.errors[0].path == "$"
    assert additional.errors[0].value == {"extra": 1}
    items = outputguard.validate("[0,1]", {"items": [True], "additionalItems": False})
    assert items.errors[0].path == "$"
    assert items.errors[0].value == [0, 1]


def test_repeated_false_constraints_report_every_instance_location():
    result = outputguard.validate("[0,1,2]", {"items": False})
    assert [error.path for error in result.errors] == ["$[0]", "$[1]", "$[2]"]
    assert [error.value for error in result.errors] == [0, 1, 2]


@pytest.mark.parametrize("schema,data,path,schema_path,value", FALSE_CASES[:7])
def test_native_fixed_dependency_behavior_is_preserved(
    monkeypatch, schema, data, path, schema_path, value
):
    import jsonschema

    import outputguard.schema as compatibility

    original = jsonschema.Draft7Validator.descend

    def fixed_descend(self, instance, schema, path=None, schema_path=None, resolver=None):
        for error in original(
            self, instance, schema, path=path, schema_path=schema_path, resolver=resolver
        ):
            if schema is False:
                if path is not None:
                    error.path.appendleft(path)
                if schema_path is not None:
                    error.schema_path.appendleft(schema_path)
            yield error

    # Model the upstream fixed descent on the older dependency used in CI.
    if compatibility._NEEDS_FALSE_PATH_FIX:
        monkeypatch.setattr(jsonschema.Draft7Validator, "descend", fixed_descend)
    monkeypatch.setattr(compatibility, "_NEEDS_FALSE_PATH_FIX", False)
    assert compatibility.prepare_schema(schema) is schema
    result = outputguard.validate(json.dumps(data), schema)
    assert result.errors[0].path == path
    assert result.errors[0].schema_path == schema_path
    assert result.errors[0].value == value


@pytest.mark.parametrize("schema", [True, False])
def test_cli_loads_boolean_schema_files(tmp_path, schema):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))
    result = CliRunner().invoke(
        cli, ["validate", "-", "-s", str(schema_path), "-f", "json"], input="null"
    )
    assert result.exit_code == (0 if schema else 1)
    assert json.loads(result.output)["valid"] is schema
    retry = CliRunner().invoke(cli, ["retry-prompt", "-", "-s", str(schema_path)], input="not json")
    assert retry.exit_code == 0
    assert ("Any parsed value is allowed" if schema else "No value is allowed") in retry.output
