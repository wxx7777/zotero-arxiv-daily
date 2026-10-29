import importlib.util
from datetime import datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "daily_schedule_gate", Path(__file__).parents[1] / "tools/daily_schedule_gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
NOW = datetime.fromisoformat("2026-10-29T02:00:00+00:00")


def receipt(date="2026-10-29", expired=False, branch="main"):
    return {"name": f"digest-sent-{date}", "expired": expired,
            "workflow_run": {"head_branch": branch}}


def test_cloud_and_github_triggers_skip_after_actual_delivery():
    assert not gate.should_run([receipt()], NOW)


def test_successful_noop_run_without_receipt_does_not_block_delivery():
    assert gate.should_run([], NOW)


def test_previous_day_receipt_does_not_block_delivery():
    assert gate.should_run([receipt("2026-10-28")], NOW)


def test_uses_china_date_across_utc_midnight():
    before_utc_midnight = datetime.fromisoformat("2026-10-28T23:00:00+00:00")
    assert not gate.should_run([receipt()], before_utc_midnight)


def test_expired_or_other_branch_receipts_do_not_block_delivery():
    assert gate.should_run([receipt(expired=True)], NOW)
    assert gate.should_run([receipt(branch="test")], NOW)


def test_explicit_force_allows_resend():
    assert gate.should_run([receipt()], NOW, force=True)


def test_only_delivery_receipts_suppress_runs():
    artifact = receipt()
    artifact["name"] = "coverage-results"
    assert gate.should_run([artifact], NOW)
