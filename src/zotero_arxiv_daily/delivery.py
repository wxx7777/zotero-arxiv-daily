"""Record SMTP acceptance, without exposing recipients or credentials."""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def record_delivery(paper_count):
    destination = os.environ.get("DIGEST_RECEIPT_PATH")
    if not destination:
        return
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    receipt = {
        "status": "smtp_accepted",
        "date": now.date().isoformat(),
        "accepted_at": now.isoformat(),
        "paper_count": paper_count,
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"delivery_date={receipt['date']}\n")
