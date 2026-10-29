"""Deduplicate every trigger using a receipt created after SMTP acceptance."""

import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo


def should_run(artifacts, now, force=False, default_branch="main"):
    if force:
        return True
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    return not any(
        artifact["name"] == f"digest-sent-{today}"
        and not artifact["expired"]
        and artifact["workflow_run"]["head_branch"] == default_branch
        for artifact in artifacts
    )


if __name__ == "__main__":
    payload = json.load(sys.stdin)
    decision = should_run(
        payload["artifacts"],
        datetime.now(ZoneInfo("Asia/Shanghai")),
        force=os.environ.get("FORCE_RESEND", "").lower() == "true",
        default_branch=os.environ["DEFAULT_BRANCH"],
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"should_run={str(decision).lower()}\n")
    print("No delivery receipt yet; run digest." if decision else "SMTP acceptance already recorded today; skip duplicate trigger.")
