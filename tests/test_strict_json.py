import json
import math
from concurrent.futures import ThreadPoolExecutor

import pytest
from click import BadParameter
from click.testing import CliRunner

from outputguard import (
    OutputGuard,
    guarded_generate,
    repair,
    validate,
    validate_and_repair,
    validate_batch,
)
from outputguard.cli import _load_schema, cli
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import FormatParseError, parse_document
from outputguard.strategies.fix_booleans import apply as fix_booleans
from outputguard.strategies.fix_values import apply as fix_values

TOKENS = ["NaN", "Infinity", "-Infinity", "+Infinity", "-NaN", "+NaN", "undefined"]
REPLACEMENTS = {**dict.fromkeys(TOKENS), "True": True, "False": False, "None": None}


def document(token, position):
    if position == "property":
        return '{"value": ' + token + "}", {"value": None}
    if position == "items":
        return "[" + token + "]", [None]
    if position == "nested":
        return '{"items": [{"value": ' + token + "}]}", {"items": [{"value": None}]}
    return token, None


@pytest.mark.parametrize("token", TOKENS)
@pytest.mark.parametrize("position", ["root", "property", "items", "nested"])
@pytest.mark.parametrize("schema", [True, False, {}])
def test_bare_constants_are_parse_failures_before_schema_validation(token, position, schema):
    text, _ = document(token, position)
    result = validate(text, schema)
    assert not result.valid and result.parse_error and not result.repaired
    assert result.data is None
    assert [(error.path, error.schema_path) for error in result.errors] == [("$", "")]
    assert result.original_text == text


@pytest.mark.parametrize("token", TOKENS)
@pytest.mark.parametrize("position", ["root", "property", "items", "nested"])
@pytest.mark.parametrize("schema", [True, False])
def test_repair_replaces_constants_then_checks_the_schema(token, position, schema):
    text, data = document(token, position)
    result = validate_and_repair(text, schema)
    assert result.valid is schema
    assert result.repaired and result.parse_error is None
    assert result.data == data and result.original_text == text
    assert result.strategies_applied == ["fix_values"]
    assert json.loads(result.repaired_text) == data
    if not schema:
        assert [(error.path, error.value) for error in result.errors] == [("$", data)]


@pytest.mark.parametrize("token", list(REPLACEMENTS))
@pytest.mark.parametrize("slashes", range(7))
def test_bare_value_scanners_preserve_strings_and_escaped_backslashes(token, slashes):
    data = {"path": "tail" + "\\" * slashes, "literal": token, "value": REPLACEMENTS[token]}
    template = json.dumps({**data, "value": None}, separators=(",", ":"))
    text = template.replace('"value":null', '"value":' + token)
    fixed = fix_values(fix_booleans(text))
    assert fixed == json.dumps(data, separators=(",", ":"))
    result = validate_and_repair(text, {})
    assert result.valid and result.data == data


@pytest.mark.parametrize("token", list(REPLACEMENTS))
@pytest.mark.parametrize("affix", ["word", "_", "$", "Ω", ".member"])
@pytest.mark.parametrize("side", ["before", "after"])
def test_repair_does_not_replace_fragments_of_other_atoms(token, affix, side):
    atom = affix + token if side == "before" else token + affix
    text = '{"value": ' + atom + "}"
    assert fix_values(fix_booleans(text)) == text


@pytest.mark.parametrize("token", TOKENS)
@pytest.mark.parametrize("schema", [True, False])
def test_disabling_value_repairs_keeps_parse_error_classification(token, schema):
    guard = OutputGuard(strategies=[])
    with pytest.raises(ParseError) as caught:
        guard.parse(token, schema)
    assert caught.value.original_text == token
    with pytest.raises(SchemaValidationError):
        OutputGuard().parse(token, False)


@pytest.mark.parametrize("format", ["auto", "forced-json-off", "yaml"])
@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_non_json_formats_can_treat_bare_names_as_strings(token, format):
    result = validate_and_repair(token, {"type": "string"}, format=format)
    assert result.valid and result.data == token
    assert not result.repaired and result.parse_error is None


@pytest.mark.parametrize(
    "text", ["0", "-0", "0.3", "1e300", "1e-300", "-1.25e+4", "1e400", "-1e400"]
)
def test_ordinary_number_syntax_remains_native(text):
    result = validate(text, True)
    assert result.valid and result.parse_error is None
    assert result.data == json.loads(text)
    assert not repair(text).repaired


@pytest.mark.parametrize(
    "format,text",
    [
        ("yaml", ".nan"),
        ("yaml", ".inf"),
        ("yaml", "-.inf"),
        ("toml", "value = nan"),
        ("toml", "value = inf"),
        ("toml", "value = -inf"),
    ],
)
def test_other_format_nonfinite_syntax_is_not_reinterpreted_as_json(format, text):
    result = validate_and_repair(text, True, format=format)
    assert result.valid and not result.repaired
    value = result.data["value"] if format == "toml" else result.data
    assert math.isnan(value) or math.isinf(value)


@pytest.mark.parametrize("schema", [True, False])
@pytest.mark.parametrize("do_repair", [True, False])
def test_batch_counts_distinguish_parse_failures_and_repaired_nulls(schema, do_repair):
    result = validate_batch(TOKENS[:3], schema, repair=do_repair)
    assert result.summary.valid == (3 if schema and do_repair else 0)
    assert result.summary.parse_failures == (0 if do_repair else 3)
    assert result.summary.schema_failures == (3 if do_repair and not schema else 0)
    assert result.summary.repaired == (3 if do_repair else 0)


def test_repaired_null_schema_failures_are_used_in_generation_feedback():
    schema = {"properties": {"value": {"type": "number"}}}

    def generate(prompt, context):
        if context.attempt == 0:
            return '{"value": NaN}'
        previous = context.previous_result
        assert previous.repaired and previous.parse_error is None
        assert previous.data == {"value": None}
        assert "$.value" in prompt
        return '{"value": 1}'

    result = guarded_generate(prompt="Return JSON", schema=schema, generate=generate)
    assert result.valid and result.data == {"value": 1}
    assert len(result.attempts) == 2


def test_quoted_constants_and_native_json_decoder_are_unchanged():
    text = '{"NaN":"Infinity","value":"\\u004e\\u0061\\u004e"}'
    result = validate_and_repair(text, {})
    assert result.valid and not result.repaired
    assert result.data == {"NaN": "Infinity", "value": "NaN"}
    assert math.isnan(json.loads("NaN"))


def test_shared_decoder_recovers_after_errors_across_threads():
    def decode(index):
        with pytest.raises(FormatParseError):
            parse_document('{"key' + str(index) + '":NaN}')
        return parse_document('{"value":' + str(index) + "}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(decode, range(64))) == [{"value": i} for i in range(64)]


@pytest.mark.parametrize("token", TOKENS[:3])
@pytest.mark.parametrize("do_repair", [False, True])
def test_cli_validation_uses_strict_json(tmp_path, token, do_repair):
    schema = tmp_path / "schema.json"
    schema.write_text("true")
    args = ["validate", "-", "-s", str(schema), "--format", "json"]
    if do_repair:
        args.append("--repair")
    result = CliRunner().invoke(cli, args, input=token)
    assert result.exit_code == (0 if do_repair else 1)
    payload = json.loads(result.output)
    assert payload["valid"] is do_repair and payload["repaired"] is do_repair
    assert (payload["parse_error"] is not None) is not do_repair


@pytest.mark.parametrize("token", TOKENS[:3])
def test_cli_schema_files_reject_nonstandard_constants(tmp_path, token):
    path = tmp_path / "schema.json"
    path.write_text('{"default":' + token + "}")
    with pytest.raises(BadParameter, match="Invalid JSON schema file"):
        _load_schema(str(path))
