import pytest

from benchmarks.unicode_repairs import METHODS, applicable_cases, run_unicode_case, unicode_cases


@pytest.mark.parametrize(
    "case,method",
    [
        pytest.param(case, method, id=f"{method}-{case['name']}")
        for method in METHODS
        for case in applicable_cases(unicode_cases(), method)
    ],
)
def test_unicode_repair_contract(case, method):
    run_unicode_case(case, method)
