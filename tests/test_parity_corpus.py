import json

import pytest

from benchmarks.comparison import assert_json_equal
from benchmarks.run import CASES_PATH, normalized, run_case


@pytest.mark.parametrize("case", json.loads(CASES_PATH.read_text()), ids=lambda case: case["name"])
def test_shared_parity_corpus(case):
    assert_json_equal(normalized(run_case(case)), case["expected"], case["name"])
