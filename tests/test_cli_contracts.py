import pytest

from benchmarks.cli_cases import cli_cases, run_cli_case


@pytest.mark.parametrize("case", cli_cases(), ids=lambda case: case["name"])
def test_cli_contract(case):
    run_cli_case(case)
