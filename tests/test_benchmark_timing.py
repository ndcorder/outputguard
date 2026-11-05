import json

import pytest

from benchmarks import run, timing


@pytest.mark.parametrize("clock,expected", [("wall", 100), ("cpu", 20)])
def test_runner_uses_selected_clock_and_observes_environment_outside_timings(
    clock, expected, capsys
):
    wall = iter([10_000, 210_000])
    cpu = iter([10_000, 50_000])
    frames = iter(
        [
            {"logical_cpus": 8, "load_average": [1, 2, 3]},
            {"logical_cpus": 8, "load_average": [4, 5, 6]},
        ]
    )
    run.main(
        ["--case", "clean_json", "--iterations", "2", "--samples", "1", "--clock", clock],
        timer_factory=lambda selected: timing.make_timer(
            selected, wall_now=lambda: next(wall), cpu_now=lambda: next(cpu)
        ),
        snapshot=lambda: next(frames),
    )
    report = json.loads(capsys.readouterr().out)
    assert report["clock"] == clock
    assert report["measurements"] == [
        {
            "name": "clean_json",
            "schema_mode": "reused",
            "median_us": expected,
            "min_us": expected,
        }
    ]
    assert report["environment"] == {
        "start": {"logical_cpus": 8, "load_average": [1, 2, 3]},
        "end": {"logical_cpus": 8, "load_average": [4, 5, 6]},
    }


@pytest.mark.parametrize("clock", ["wall", "cpu"])
def test_reported_microseconds_round_positive_half_up(clock, capsys):
    readings = iter([0, 2_469_000])
    run.main(
        ["--case", "clean_json", "--iterations", "2000", "--samples", "1", "--clock", clock],
        timer_factory=lambda selected: lambda: next(readings),
        snapshot=lambda: None,
    )
    result = json.loads(capsys.readouterr().out)
    assert result["measurements"][0]["median_us"] == 1.235
    assert result["measurements"][0]["min_us"] == 1.235


@pytest.mark.parametrize("clock", ["wall", "cpu"])
def test_results_mode_does_not_read_clocks_or_collect_environment(clock, capsys):
    def forbidden(*args):
        raise AssertionError("Results mode should only check correctness")

    run.main(
        ["--case", "clean_json", "--results", "--clock", clock],
        timer_factory=forbidden,
        snapshot=forbidden,
    )
    results = json.loads(capsys.readouterr().out)
    assert len(results) == 1 and results[0]["name"] == "clean_json"
    assert "clock" not in results[0] and "environment" not in results[0]


@pytest.mark.parametrize("clock", ["monotonic", "CPU", None, False, [], {}])
def test_clock_factory_rejects_unknown_clocks(clock):
    with pytest.raises(ValueError, match="clock must be wall or cpu"):
        timing.make_timer(clock)


@pytest.mark.parametrize("missing", [False, True])
def test_missing_or_unavailable_load_is_not_reported_as_zero(monkeypatch, missing):
    monkeypatch.setattr(timing.os, "cpu_count", lambda: None)
    if missing:
        monkeypatch.delattr(timing.os, "getloadavg", raising=False)
    else:

        def unavailable():
            raise OSError("unavailable")

        monkeypatch.setattr(timing.os, "getloadavg", unavailable, raising=False)
    assert timing.environment_snapshot() == {"logical_cpus": None, "load_average": None}


def test_environment_snapshots_copy_provider_values(monkeypatch):
    load = [1, 2, 3]
    monkeypatch.setattr(timing.os, "getloadavg", lambda: load, raising=False)
    monkeypatch.setattr(timing.os, "cpu_count", lambda: 8)
    snapshot = timing.environment_snapshot()
    load[0] = 99
    assert snapshot == {"logical_cpus": 8, "load_average": [1, 2, 3]}


@pytest.mark.parametrize(
    "value,expected", [("1", 1), ("+0002", 2), (" 3\n", 3), (str(2**53 - 1), 2**53 - 1)]
)
def test_iteration_counts_accept_portable_decimal_safe_integers(value, expected):
    assert run.positive_int(value) == expected
