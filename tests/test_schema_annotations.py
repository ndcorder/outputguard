import asyncio
import json

import pytest
from click.testing import CliRunner

import outputguard
from outputguard.cli import cli


@pytest.mark.parametrize(
    "annotation", [True, False, None, 0, 1, "annotation", [], {}, {"type": "integer"}]
)
def test_async_annotations_do_not_change_validation(annotation):
    schema = {"$async": annotation, "type": "integer"}
    assert outputguard.validate("42", schema).valid is True
    failed = outputguard.validate('"wrong"', schema)
    assert failed.valid is False
    assert failed.errors[0].path == "$"
    assert failed.errors[0].value == "wrong"


@pytest.mark.parametrize("annotation", [False, True])
def test_boolean_annotation_reference_targets(annotation):
    schema = {
        "$async": annotation,
        "$ref": "#/$async",
        "definitions": {"unused": {"$async": True}},
    }
    for text in ["null", "42", '"text"', "{}", "[]"]:
        assert outputguard.validate(text, schema).valid is annotation


@pytest.mark.parametrize("reference", ["#/$async", "#/%24async", "#/$async/definitions/integer"])
def test_references_into_annotations(reference):
    schema = {
        "$async": {
            "$async": True,
            "type": "integer",
            "definitions": {"integer": {"$async": True, "type": "integer"}},
        },
        "$ref": reference,
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_schemas_referenced_inside_metadata_arrays():
    schema = {
        "$async": [True, False, {"$async": True, "type": "integer"}],
        "$ref": "#/$async/2",
    }
    assert outputguard.validate("42", schema).valid
    assert not outputguard.validate('"wrong"', schema).valid


def test_literal_constants_can_also_be_used_as_schemas():
    literal = {"$async": True, "type": "integer"}
    schema = {
        "definitions": {"holder": {"const": literal}},
        "anyOf": [
            {"$ref": "#/definitions/holder/const"},
            {"$ref": "#/definitions/holder"},
        ],
    }
    before = json.dumps(schema)
    for _ in range(3):
        assert outputguard.validate("42", schema).valid
        assert outputguard.validate(json.dumps(literal), schema).valid
        assert not outputguard.validate('{"type":"integer"}', schema).valid
        assert not outputguard.validate('"wrong"', schema).valid
    assert json.dumps(schema) == before


def test_recursive_schemas_referenced_from_literal_annotations():
    schema = {
        "const": {
            "$async": True,
            "properties": {"value": {"type": "integer"}, "next": {"$ref": "#/const"}},
        },
        "$ref": "#/const",
    }
    assert outputguard.validate('{"value":1,"next":{"value":2}}', schema).valid
    failed = outputguard.validate('{"value":1,"next":{"value":"wrong"}}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.next.value"


def test_false_subschemas_referenced_from_annotations_keep_their_paths():
    schema = {"$async": {"properties": {"blocked": False}}, "$ref": "#/$async"}
    failed = outputguard.validate('{"blocked":1}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.blocked"
    assert failed.errors[0].value == 1
    assert schema["$async"]["properties"]["blocked"] is False


def test_prototype_named_constraints_in_referenced_annotations():
    schema = {
        "$async": {
            "properties": {"__proto__": {"type": "integer"}},
            "dependencies": {"__proto__": ["needed"]},
        },
        "$ref": "#/$async",
    }
    assert outputguard.validate('{"__proto__":42,"needed":true}', schema).valid
    failed = outputguard.validate('{"__proto__":"wrong","needed":true}', schema)
    assert not failed.valid
    assert failed.errors[0].path == "$.__proto__"
    assert len(outputguard.validate('{"__proto__":42}', schema).errors) == 1


def test_annotated_documents_keep_identifiers_and_recursion_local():
    def document(type_name):
        return {
            "$id": "constructor",
            "$async": True,
            "properties": {"value": {"type": type_name}, "next": {"$ref": "#"}},
        }

    assert outputguard.validate('{"value":1,"next":{"value":2}}', document("integer")).valid
    assert outputguard.validate('{"value":"a","next":{"value":"b"}}', document("string")).valid
    assert not outputguard.validate(
        '{"value":1,"next":{"value":"wrong"}}', document("integer")
    ).valid


def test_annotation_names_resembling_javascript_compilation_keywords_do_not_collide():
    schema = {
        "$async": {"type": "integer"},
        "outputguardAsync0": {"type": "string"},
        "properties": {
            "integer": {"$ref": "#/$async"},
            "string": {"$ref": "#/outputguardAsync0"},
        },
    }
    assert outputguard.validate('{"integer":42,"string":"text"}', schema).valid
    assert not outputguard.validate('{"integer":"wrong"}', schema).valid
    assert not outputguard.validate('{"string":42}', schema).valid


def test_annotated_schema_failures_reach_parsing_repairs_and_batches():
    schema = {"$async": True, "type": "integer"}
    assert outputguard.OutputGuard().validate("42", schema).valid
    assert outputguard.parse("42", schema) == 42
    with pytest.raises(outputguard.SchemaValidationError):
        outputguard.parse('"wrong"', schema)
    repaired = outputguard.validate_and_repair('```json\n"wrong"\n```', schema)
    assert not repaired.valid
    assert repaired.repaired
    assert repaired.repaired_text == '"wrong"'
    batch = outputguard.validate_batch(["42", '"wrong"', "not JSON"], schema)
    assert batch.summary.valid == 1
    assert batch.summary.schema_failures == 1
    assert batch.summary.parse_failures == 1


def test_annotated_schema_failures_feed_generation_retries():
    schema = {"$async": True, "type": "integer"}
    result = outputguard.guarded_generate(
        prompt="Return an integer",
        schema=schema,
        generate=lambda _prompt, context: '"wrong"' if context.attempt == 0 else "42",
    )
    assert result.valid
    assert len(result.attempts) == 2

    async def generate(_prompt, context):
        return '"wrong"' if context.attempt == 0 else "42"

    async_result = asyncio.run(
        outputguard.guarded_generate_async(
            prompt="Return an integer", schema=schema, generate=generate
        )
    )
    assert async_result.valid
    assert len(async_result.attempts) == 2


def test_cli_reports_invalid_annotated_schema_values(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps({"$async": True, "type": "integer"}))
    result = CliRunner().invoke(
        cli, ["validate", "-", "-s", str(path), "--format", "json"], input='"wrong"'
    )
    assert result.exit_code == 1
    assert json.loads(result.output)["valid"] is False
