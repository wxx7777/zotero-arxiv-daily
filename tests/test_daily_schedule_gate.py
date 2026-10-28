import importlib.util
from datetime import datetime
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "daily_schedule_gate", Path(__file__).parents[1] / "tools/daily_schedule_gate.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
NOW = datetime.fromisoformat("2026-10-28T02:17:00+00:00")


def run(created_at, conclusion="success", run_id=1):
    return {"id": run_id, "conclusion": conclusion, "created_at": created_at}


def test_retry_skips_after_success_today():
    assert not gate.should_run("schedule", [run("2026-10-28T02:00:00Z")], 2, NOW)


def test_previous_day_success_does_not_block_next_digest():
    assert gate.should_run("schedule", [run("2026-10-27T02:00:00Z")], 2, NOW)


def test_uses_china_date_across_utc_midnight():
    assert not gate.should_run("schedule", [run("2026-10-27T23:00:00Z")], 2, NOW)


def test_failed_or_missing_runs_allow_retry():
    assert gate.should_run("schedule", [], 2, NOW)
    assert gate.should_run("schedule", [run("2026-10-28T02:00:00Z", "failure")], 2, NOW)


def test_manual_runs_can_still_test_or_resend():
    assert gate.should_run("workflow_dispatch", [run("2026-10-28T02:00:00Z")], 2, NOW)


def test_current_run_does_not_block_itself():
    assert gate.should_run("schedule", [run("2026-10-28T02:00:00Z", run_id=2)], 2, NOW)
