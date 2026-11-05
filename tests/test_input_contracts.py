import asyncio

import pytest

from benchmarks.comparison import assert_json_equal
from benchmarks.input_cases import input_cases, run_input_case


@pytest.mark.parametrize("case", input_cases(), ids=lambda case: case["name"])
@pytest.mark.parametrize("asynchronous", [False, True])
def test_input_contract(case, asynchronous):
    result = asyncio.run(run_input_case(case, asynchronous=asynchronous))
    assert_json_equal(result, {"name": case["name"], **case["expected"]}, case["name"])
