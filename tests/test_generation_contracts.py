import pytest

from benchmarks.generation_cases import generation_cases, run_generation_case


@pytest.mark.parametrize("case", generation_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("throwing", [False, True])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_generation_contract(case, throwing, asynchronous):
    run_generation_case(case, throwing=throwing, asynchronous=asynchronous)
