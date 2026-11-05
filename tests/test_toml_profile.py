import hashlib
import json
import math
import multiprocessing
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from click.testing import CliRunner

from benchmarks.comparison import assert_json_equal
from outputguard import OutputGuard, validate, validate_and_repair, validate_batch
from outputguard.cli import cli
from outputguard.exceptions import ParseError, SchemaValidationError
from outputguard.formats import FormatParseError, parse_document
from outputguard.toml_profile import _runtime

ROOT = Path(__file__).parents[1]
CASES = json.loads((ROOT / "benchmarks/toml_cases.json").read_text())


def assert_value(data, case):
    if "value_kind" in case:
        value = data["value"]
        if case["value_kind"] == "nan":
            assert math.isnan(value)
        else:
            assert value == (-math.inf if case["value_kind"] == "negative_infinity" else math.inf)
    else:
        assert_json_equal(data, case["value"], case["name"])
    if "number_type" in case:
        value = data["value"]
        assert type(value) is (int if case["number_type"] == "integer" else float)
        if value == 0:
            assert math.copysign(1, value) == math.copysign(1, case["value"]["value"])


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_toml_profile_data_and_parse_failure_categories(case):
    for schema in (True, False):
        result = validate(case["text"], schema, format="toml")
        assert result.original_text == case["text"] and not result.repaired
        assert result.strategies_applied == []
        if case["valid"]:
            assert result.valid is schema and result.parse_error is None
            assert_value(result.data, case)
            assert [error.path for error in result.errors] == ([] if schema else ["$"])
        else:
            assert not result.valid and result.data is None and result.parse_error
            assert [(error.path, error.schema_path) for error in result.errors] == [("$", "")]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_toml_parser_and_repair_short_circuit(case):
    if not case["valid"]:
        with pytest.raises(FormatParseError):
            parse_document(case["text"], "toml")
        return
    assert_value(parse_document(case["text"], "toml"), case)
    result = validate_and_repair(case["text"], True, format="toml")
    assert result.valid and not result.repaired and not result.strategies_applied
    assert result.repaired_text == "" and result.parse_error is None
    assert_value(result.data, case)


@pytest.mark.parametrize("format", ["toml", "auto", "forced-json-off", " TOML "])
def test_date_strings_use_schema_type_format_and_reference_validation(format):
    text = 'date = 2026-11-04\nstamp = 2026-11-04t12:34:56.123456789z\n"__proto__" = {time=12:34}'
    schema = {
        "type": "object",
        "definitions": {"date": {"type": "string", "format": "date"}},
        "properties": {
            "date": {"$ref": "#/definitions/date"},
            "stamp": {"type": "string", "format": "date-time"},
            "__proto__": {"properties": {"time": {"type": "string", "const": "12:34:00"}}},
        },
    }
    result = validate(text, schema, format=format)
    assert result.valid and result.format == format
    assert result.data["stamp"] == "2026-11-04T12:34:56.123456789Z"
    schema["properties"]["stamp"] = {"type": "object"}
    result = validate(text, schema, format=format)
    assert result.parse_error is None and [error.path for error in result.errors] == ["$.stamp"]


def test_toml_guard_batch_and_cli_date_serialization(tmp_path):
    text = "value=2026-11-04T12:34:56.123456789Z"
    schema = {"properties": {"value": {"type": "string", "format": "date-time"}}}
    guard = OutputGuard(format="toml", strategies=[])
    assert guard.parse(text, schema) == {"value": "2026-11-04T12:34:56.123456789Z"}
    with pytest.raises(ParseError):
        guard.parse("value=2026-02-30", schema)
    with pytest.raises(SchemaValidationError):
        guard.parse('value="bad"', schema)
    summary = validate_batch([text, 'value="bad"', "value=2026-02-30"], schema, guard=guard).summary
    assert summary.valid == 1 and summary.parse_failures == 1 and summary.schema_failures == 1
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(schema))
    result = CliRunner().invoke(
        cli,
        ["validate", "-", "-s", str(schema_path), "--input-format", "toml", "-f", "json"],
        input=text,
    )
    assert result.exit_code == 0, result.output
    assert "2026-11-04T12:34:56.123456789Z" in result.output


def test_toml_input_is_data_and_runtime_survives_errors():
    payload = '"; globalThis.compromised = true; //'
    assert parse_document("value=" + json.dumps(payload), "toml") == {"value": payload}
    assert _runtime().context.eval("typeof globalThis.compromised") == "undefined"
    for text in ("value=2026-02-30", "value=\ud800", "value=", "a=1\na=2"):
        with pytest.raises(FormatParseError):
            parse_document(text, "toml")
        assert parse_document("value=12:34", "toml") == {"value": "12:34:00"}
    for encoded in ("null", "[]", "{}", "true", "123", "invalid"):
        assert json.loads(_runtime().parse(encoded))["ok"] is False


def test_toml_contexts_are_isolated_by_thread():
    barrier = threading.Barrier(8)

    def worker(index):
        data = parse_document(f"id={index}\ndate=2026-11-04", "toml")
        runtime = _runtime()
        barrier.wait(timeout=10)
        return id(runtime.context), data

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(worker, range(8)))
    assert len({context for context, data in results}) == 8
    assert [data["id"] for context, data in results] == list(range(8))


def _forked_toml(connection):
    try:
        connection.send((_runtime().pid, parse_document("value=12:34", "toml")))
    finally:
        connection.close()


@pytest.mark.skipif("fork" not in multiprocessing.get_all_start_methods(), reason="requires fork")
def test_toml_runtime_is_reset_after_fork():
    assert _runtime().pid == os.getpid()
    parent, child = multiprocessing.get_context("fork").Pipe(duplex=False)
    process = multiprocessing.get_context("fork").Process(target=_forked_toml, args=(child,))
    process.start()
    child.close()
    try:
        assert parent.poll(10)
        pid, data = parent.recv()
        assert pid == process.pid and pid != os.getpid() and data == {"value": "12:34:00"}
    finally:
        parent.close()
        process.join(10)
        if process.is_alive():
            process.kill()
            process.join()
    assert process.exitcode == 0


def test_toml_bundled_engine_matches_its_manifest():
    package = ROOT / "outputguard"
    metadata = json.loads((package / "_toml_engine.json").read_text())
    assert (
        hashlib.sha256((package / "_toml_engine.js").read_bytes()).hexdigest()
        == metadata["bundle_sha256"]
    )
