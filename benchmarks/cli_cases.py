"""Run CLI contracts with separate stdout/stderr and native field-name normalization."""

from __future__ import annotations

import inspect
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from benchmarks.comparison import assert_json_equal

CASES_PATH = Path(__file__).with_name("cli_cases.json")
_FIELDS = {
    "original_text": "originalText",
    "repaired_text": "repairedText",
    "strategies_applied": "strategiesApplied",
    "parse_error": "parseError",
    "parse_failures": "parseFailures",
    "schema_failures": "schemaFailures",
    "success_rate": "successRate",
    "strategy_counts": "strategyCounts",
}


def cli_cases() -> list[dict]:
    cases = json.loads(CASES_PATH.read_text())
    for index, case in enumerate(cases):
        if "large" not in case:
            continue
        value = case["large"]["token"] * case["large"]["count"]
        text = json.dumps({"value": value}, ensure_ascii=False, separators=(",", ":"))

        def expand(item, value=value, text=text):
            if isinstance(item, str):
                return {"__LARGE_VALUE__": value, "__LARGE_DOCUMENT__": text}.get(item, item)
            if isinstance(item, list):
                return [expand(child) for child in item]
            if isinstance(item, dict):
                return {key: expand(child) for key, child in item.items()}
            return item

        cases[index] = expand(case)
    return cases


def _get(value: dict, key: str):
    return value[key] if key in value else value[_FIELDS.get(key, key)]


def _validation(value):
    errors = sorted(value["errors"], key=lambda error: error["path"])
    return {
        "valid": value["valid"],
        "data": value["data"],
        "repaired": value["repaired"],
        "repaired_text": _get(value, "repaired_text"),
        "strategies": _get(value, "strategies_applied"),
        "parse_failure": _get(value, "parse_error") is not None,
        "error_paths": [error["path"] for error in errors],
        "error_values": [error.get("value") for error in errors],
        "original_text": _get(value, "original_text"),
        "format": value["format"],
    }


def _invalid_constant(token):
    raise ValueError(f"Non-standard constant in CLI JSON output: {token}")


def normalize_output(text: str, kind: str):
    if kind == "none":
        if text:
            raise ValueError(f"Unexpected CLI stdout: {text[:200]!r}")
        return None
    if kind == "text":
        return text
    if kind == "help":
        if "Usage:" not in text:
            raise ValueError("CLI help did not contain a usage line")
        return "help"
    if kind == "prompt":
        label = re.match(r"The (.+) output you provided", text)
        if label is None:
            raise ValueError("CLI retry prompt is missing its format label")
        footer = f"\n\nReturn ONLY the corrected {label[1]}.\n"
        if not text.endswith(footer):
            raise ValueError("CLI retry prompt is incomplete")
        history = "\nOriginal output:\n" in text
        body = text[: -len(footer)]
        summary = (
            body.split("\nThe expected schema requires:\n", 1)[1].split(
                "\n\nOriginal output:\n", 1
            )[0]
            if "\nThe expected schema requires:\n" in body
            else None
        )
        return {
            "label": label[1],
            "paths": re.findall(r"(?m)^\d+\. At ([^:]+):", text),
            "history": history,
            "summary": summary,
            "original": text.split("\nOriginal output:\n", 1)[1][: -len(footer)]
            if history
            else None,
        }
    value = json.loads(text, parse_constant=_invalid_constant)
    if kind == "validation":
        return _validation(value)
    if kind == "repair":
        return {
            "repaired": value["repaired"],
            "text": value["text"],
            "strategies": _get(value, "strategies_applied"),
            "parse_failure": _get(value, "parse_error") is not None,
            "format": value["format"],
        }
    if kind == "batch":
        summary = value["summary"]
        return {
            "summary": {
                key: _get(summary, key)
                for key in (
                    "total",
                    "valid",
                    "invalid",
                    "repaired",
                    "parse_failures",
                    "schema_failures",
                    "success_rate",
                    "strategy_counts",
                    "formats",
                )
            },
            "results": [
                {**_validation(item), "index": item["index"], "input": item["input"]}
                for item in value["results"]
            ],
        }
    raise ValueError(f"Unknown CLI output kind: {kind}")


def _bytes(value):
    return bytes.fromhex(value["hex"]) if isinstance(value, dict) else value.encode("utf-8")


def run_cli_case(
    case: dict, command: list[str] | None = None, durations: list[float] | None = None
) -> dict:
    with tempfile.TemporaryDirectory(prefix="outputguard-cli-") as directory:
        root = Path(directory)
        for name, contents in case["files"].items():
            path = root / name
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("CLI fixture files must stay inside their temporary directory")
            path.write_bytes(_bytes(contents))
        if command is None:
            from click.testing import CliRunner

            from outputguard.cli import cli

            # Click 8.1 needs an explicit switch to retain the two streams.
            options = (
                {"mix_stderr": False}
                if "mix_stderr" in inspect.signature(CliRunner).parameters
                else {}
            )
            runner = CliRunner(**options)
            previous = Path.cwd()
            try:
                os.chdir(root)
                result = runner.invoke(
                    cli,
                    case["args"],
                    input=_bytes(case.get("stdin", "")),
                    prog_name="outputguard",
                    env={"NO_COLOR": "1", "FORCE_COLOR": "0"},
                )
                code, stdout, stderr = result.exit_code, result.stdout_bytes, result.stderr_bytes
            finally:
                os.chdir(previous)
        else:
            environment = {**os.environ, "NO_COLOR": "1"}
            environment.pop("FORCE_COLOR", None)
            started = time.perf_counter_ns() if durations is not None else 0
            result = subprocess.run(
                [*command, *case["args"]],
                cwd=root,
                input=_bytes(case.get("stdin", "")),
                capture_output=True,
                timeout=30,
                check=False,
                env=environment,
            )
            if durations is not None:
                durations.append((time.perf_counter_ns() - started) / 1000)
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        for fragment in case.get("stderr_contains", []):
            assert fragment.encode("utf-8") in stderr, (
                f"{case['name']}: stderr lost literal details"
            )
        if b"Traceback (most recent call last)" in stderr:
            raise ValueError(f"CLI exposed a traceback: {stderr[:1000]!r}")
        file = root / case.get("output_file", "result.txt")
        actual = {
            "code": code,
            "stdout": normalize_output(stdout.decode("utf-8"), case["kind"]),
            "stderr": bool(stderr),
            "file": normalize_output(
                file.read_bytes().decode("utf-8"), case.get("file_kind", "text")
            )
            if file.exists()
            else None,
        }
        assert_json_equal(actual, case["expected"], case["name"])
        return {"name": case["name"], **actual}
