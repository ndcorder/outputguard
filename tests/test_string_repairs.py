import pytest

from benchmarks.string_repairs import (
    METHODS,
    applicable_cases,
    run_string_repair_case,
    string_repair_cases,
)


@pytest.mark.parametrize(
    "case,method",
    [
        pytest.param(case, method, id=f"{method}-{case['name']}")
        for method in METHODS
        for case in applicable_cases(string_repair_cases(), method)
    ],
)
def test_string_repair_contract(case, method):
    run_string_repair_case(case, method)
