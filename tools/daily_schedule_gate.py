"""Skip scheduled retries after a successful digest on the same China date."""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


def should_run(event_name, runs, current_run_id, now):
    if event_name != "schedule":
        return True
    china = ZoneInfo("Asia/Shanghai")
    today = now.astimezone(china).date()
    for run in runs:
        if str(run["id"]) == str(current_run_id) or run["conclusion"] != "success":
            continue
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created.astimezone(china).date() == today:
            return False
    return True


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    decision = should_run(
        os.environ["GITHUB_EVENT_NAME"],
        payload["workflow_runs"],
        os.environ["GITHUB_RUN_ID"],
        datetime.now(ZoneInfo("Asia/Shanghai")),
    )
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.write(f"should_run={str(decision).lower()}\n")
    print("Run today's digest." if decision else "Today's digest already succeeded; skip retry.")
