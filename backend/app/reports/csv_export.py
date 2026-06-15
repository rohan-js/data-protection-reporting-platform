from __future__ import annotations

import csv
import uuid
from pathlib import Path

from app.config import settings
from app.storage import db


def generate_csv_report(start: str | None = None, end: str | None = None) -> dict[str, str]:
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    report_id = str(uuid.uuid4())
    path = settings.report_dir / f"{report_id}.csv"
    rows = db.list_rows("anomalies", limit=5000)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["id", "event_id", "severity", "anomaly_type", "subject", "description", "detected_at", "acknowledged"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "id": report_id,
        "report_type": "CSV",
        "generated_at": db.utc_now(),
        "time_range_start": start,
        "time_range_end": end,
        "file_path": str(path),
    }
    db.save_report(report)
    return report
