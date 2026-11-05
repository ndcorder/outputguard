import itertools
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from benchmarks.comparison import assert_json_equal
from benchmarks.diff_cases import apply_patch, diff_cases, run_diff_case
from outputguard.report import RepairReport


@pytest.mark.parametrize("case", diff_cases(), ids=lambda case: case["name"])
def test_exact_diff_contract(case):
    assert_json_equal(run_diff_case(case), case["expected"], case["name"])


def test_small_sequences_have_minimal_edits_and_reversible_patches():
    values = [
        "".join(parts)
        for n in range(5)
        for parts in itertools.product(["a\n", "b\n", "c\n"], repeat=n)
    ]
    for before in values:
        for after in values:
            a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
            row = [0] * (len(b) + 1)
            for x in a:
                next_row = [0]
                for j, y in enumerate(b):
                    next_row.append(row[j] + 1 if x == y else max(row[j + 1], next_row[-1]))
                row = next_row
            patch = RepairReport(before, after, True).diff
            edits = sum(line.startswith(("+", "-")) for line in patch.split("\n")[2:])
            assert edits == len(a) + len(b) - 2 * row[-1]
            assert apply_patch(before, patch) == after
            assert apply_patch(after, patch, reverse=True) == before


def test_work_limit_falls_back_to_a_valid_patch(monkeypatch):
    monkeypatch.setattr("outputguard._diff._MAX_WORK", 1)
    before = "prefix\nold\nsame\nsame\nlast\nsuffix\n"
    after = "prefix\nnew\nsame\nsame\nLAST\nsuffix\n"
    patch = RepairReport(before, after, True).diff
    assert "-same\n-same\n" in patch and "+same\n+same\n" in patch
    assert apply_patch(before, patch) == after
    assert apply_patch(after, patch, reverse=True) == before


@pytest.mark.skipif(
    shutil.which("git") is None, reason="Git is needed for an independent patch check"
)
def test_patches_apply_and_reverse_with_git():
    with tempfile.TemporaryDirectory(prefix="outputguard-diff-") as directory:
        root = Path(directory)
        for case in diff_cases():
            patch = case["expected"]["diff"]
            if not patch:
                continue
            try:
                before, after = case["before"].encode("utf-8"), case["after"].encode("utf-8")
            except UnicodeEncodeError:
                continue  # Native strings with unpaired surrogates are not UTF-8 files.
            (root / "data").write_bytes(before)
            payload = ("--- a/data\n+++ b/data\n" + patch.split("\n", 2)[2]).encode("utf-8")
            for reverse, expected in ((False, after), (True, before)):
                command = [
                    "git",
                    "-c",
                    "core.autocrlf=false",
                    "-c",
                    "apply.whitespace=nowarn",
                    "apply",
                    "--unsafe-paths",
                ]
                if reverse:
                    command.append("--reverse")
                completed = subprocess.run(
                    command, cwd=root, input=payload, capture_output=True, timeout=10
                )
                assert completed.returncode == 0, (case["name"], completed.stderr)
                assert (root / "data").read_bytes() == expected, case["name"]
