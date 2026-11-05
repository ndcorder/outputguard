"""Exact diff contracts and an independent, strict unified-patch reader."""

import json
import re
from pathlib import Path

from benchmarks.comparison import assert_json_equal
from outputguard.report import RepairReport, StrategyApplication

CASES_PATH = Path(__file__).with_name("diff_cases.json")


def diff_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text())


def _lines(text):
    return re.findall(r"[^\n]*\n|[^\n]+\Z", text)


def apply_patch(text: str, patch: str, *, reverse: bool = False) -> str:
    """Check ranges, context, deletions, and newline markers while applying a patch."""
    if not patch:
        return text
    lines = _lines(patch)
    assert lines[0].startswith("--- ") and lines[1].startswith("+++ ")
    source, result, position, index = _lines(text), [], 0, 2
    while index < len(lines):
        match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@\n", lines[index])
        assert match, (index, lines[index])
        a_start, a_count, b_start, b_count = match.groups()
        a_count, b_count = int(a_count or 1), int(b_count or 1)
        a_start, b_start = int(a_start) - bool(a_count), int(b_start) - bool(b_count)
        if reverse:
            a_start, b_start, a_count, b_count = b_start, a_start, b_count, a_count
        assert position <= a_start <= len(source)
        result.extend(source[position:a_start])
        assert len(result) == b_start
        position = a_start
        consumed = produced = 0
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            sign, value = lines[index][0], lines[index][1:]
            assert sign in " +-" and value.endswith("\n")
            index += 1
            if index < len(lines) and lines[index] == "\\ No newline at end of file\n":
                value = value[:-1]
                index += 1
            if reverse:
                sign = {"+": "-", "-": "+", " ": " "}[sign]
            if sign in " -":
                assert position < len(source) and source[position] == value
                position += 1
                consumed += 1
            if sign in " +":
                result.append(value)
                produced += 1
        assert consumed == a_count and produced == b_count
    result.extend(source[position:])
    return "".join(result)


def run_diff_case(case: dict) -> dict:
    before, after = case["before"], case["after"]
    step = StrategyApplication(
        case.get("strategy", "demo"),
        case.get("changed", before != after),
        before,
        after,
        case.get("error"),
    )
    report = RepairReport(before, after, True, steps=[step])
    result = {"diff": report.diff, "step_diff": step.diff, "details": report.step_diffs()}
    assert apply_patch(before, result["diff"]) == after
    assert apply_patch(after, result["diff"], reverse=True) == before
    if step.changed:
        assert apply_patch(before, result["step_diff"]) == after
    return result


def check_diff_cases(cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        result = run_diff_case(case)
        assert_json_equal(result, case["expected"], case["name"])
        results.append({"name": case["name"], **result})
    return results
