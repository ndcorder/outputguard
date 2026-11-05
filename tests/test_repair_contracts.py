import pytest

from benchmarks.comparison import assert_json_equal
from benchmarks.repair_cases import repair_cases, run_repair_case
from outputguard import repair


@pytest.mark.parametrize("case", repair_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("report", [False, True])
@pytest.mark.parametrize("entrypoint", ["guard", "module"])
def test_repair_contract(case, report, entrypoint):
    actual = run_repair_case(case, report=report, entrypoint=entrypoint)
    expected = {**case["expected"]}
    if not report:
        expected.pop("report")
    assert_json_equal(actual, expected, case["name"])


def test_public_report_preserves_positional_format():
    text = "```yaml\nname: Ada\n```"
    result, report = repair(text, "yaml", report=True)
    assert result == repair(text, "yaml")
    assert result.text == "name: Ada"
    assert result.format == report.format == "yaml"
    assert report.original_text == text
    assert report.success
