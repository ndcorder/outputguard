import pytest

from benchmarks.truncation_cases import (
    METHODS,
    applicable_cases,
    run_truncation_case,
    truncation_cases,
)


@pytest.mark.parametrize(
    "case,method",
    [
        pytest.param(case, method, id=f"{method}-{case['name']}")
        for method in METHODS
        for case in applicable_cases(truncation_cases(), method)
    ],
)
def test_truncation_repair_contract(case, method):
    run_truncation_case(case, method)
