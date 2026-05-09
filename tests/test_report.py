from outputguard.report import RepairReport, StrategyApplication


def test_report_no_repair_needed():
    report = RepairReport(
        original_text='{"a": 1}',
        final_text='{"a": 1}',
        success=True,
        steps=[],
    )
    assert report.confidence == 1.0
    assert report.strategies_applied == []
    assert "No repair needed" in report.summary
    assert report.diff == ""


def test_report_single_strategy():
    report = RepairReport(
        original_text='```json\n{"a": 1}\n```',
        final_text='{"a": 1}',
        success=True,
        steps=[
            StrategyApplication(
                name="strip_fences",
                changed=True,
                input_text='```json\n{"a": 1}\n```',
                output_text='{"a": 1}',
            ),
        ],
    )
    assert report.confidence > 0.5
    assert report.strategies_applied == ["strip_fences"]
    assert "strip_fences" in report.summary
    assert "original" in report.diff
    assert "repaired" in report.diff


def test_report_multiple_strategies():
    report = RepairReport(
        original_text='```json\n{name: "Alice",}\n```',
        final_text='{"name": "Alice"}',
        success=True,
        steps=[
            StrategyApplication(name="strip_fences", changed=True, input_text="a", output_text="b"),
            StrategyApplication(name="fix_commas", changed=True, input_text="b", output_text="c"),
            StrategyApplication(name="fix_keys", changed=True, input_text="c", output_text="d"),
            StrategyApplication(name="fix_values", changed=False, input_text="d", output_text="d"),
        ],
    )
    assert report.confidence < 0.8  # Multiple strategies = lower confidence
    assert report.strategies_applied == ["strip_fences", "fix_commas", "fix_keys"]
    assert report.strategies_tried == ["strip_fences", "fix_commas", "fix_keys", "fix_values"]
    assert "3" in report.summary


def test_report_failure():
    report = RepairReport(
        original_text="garbage",
        final_text="garbage",
        success=False,
        steps=[
            StrategyApplication(
                name="strip_fences", changed=False, input_text="garbage", output_text="garbage"
            ),
        ],
        parse_error="Expecting value",
    )
    assert report.confidence == 0.0
    assert "failed" in report.summary.lower()


def test_strategy_application_diff():
    step = StrategyApplication(
        name="strip_fences",
        changed=True,
        input_text='```json\n{"a": 1}\n```',
        output_text='{"a": 1}',
    )
    assert "before_strip_fences" in step.diff
    assert "after_strip_fences" in step.diff


def test_strategy_application_no_change():
    step = StrategyApplication(
        name="fix_commas",
        changed=False,
        input_text='{"a": 1}',
        output_text='{"a": 1}',
    )
    assert step.diff == ""


def test_step_diffs():
    report = RepairReport(
        original_text="in",
        final_text="out",
        success=True,
        steps=[
            StrategyApplication(name="a", changed=True, input_text="in", output_text="mid"),
            StrategyApplication(name="b", changed=False, input_text="mid", output_text="mid"),
            StrategyApplication(name="c", changed=True, input_text="mid", output_text="out"),
        ],
    )
    verbose = report.step_diffs()
    assert "=== a ===" in verbose
    assert "=== c ===" in verbose
    assert "=== b ===" not in verbose  # b didn't change
