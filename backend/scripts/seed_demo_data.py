from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.detection.anomaly import run_detection  # noqa: E402
from app.detection.scoring import recalculate_risk_scores  # noqa: E402
from app.reports.pdf_generator import generate_pdf_report  # noqa: E402
from app.storage import db  # noqa: E402


DEMO_ACCOUNT = "demo-account"
BASE_TIME = datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)


def event_payload(index: int, name: str, subject: str, identity_type: str, source_ip: str, *, error_code: str | None = None, mfa: str | None = None) -> dict[str, str | None]:
    event_time = BASE_TIME - timedelta(hours=index)
    raw = {
        "eventID": f"demo-event-{index:03d}",
        "eventName": name,
        "eventTime": event_time.isoformat(),
        "sourceIPAddress": source_ip,
        "awsRegion": "ap-south-1",
        "userIdentity": {
            "type": identity_type,
            "arn": subject,
            "userName": subject.split("/")[-1],
        },
    }
    if error_code:
        raw["errorCode"] = error_code
    if mfa is not None:
        raw["additionalEventData"] = {"MFAUsed": mfa}
    return {
        "id": raw["eventID"],
        "event_time": raw["eventTime"],
        "event_name": name,
        "user_identity": json.dumps(raw["userIdentity"]),
        "subject": subject,
        "source_ip": source_ip,
        "aws_region": "ap-south-1",
        "error_code": error_code,
        "raw": json.dumps(raw),
        "ingested_at": db.utc_now(),
    }


def seed(database_path: Path, report_dir: Path, sample_report: Path | None) -> None:
    if database_path.exists():
        database_path.unlink()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    object.__setattr__(settings, "database_path", database_path)
    object.__setattr__(settings, "report_dir", report_dir)
    db.init_db(database_path)

    identities = [
        {
            "id": "demo:user/security-analyst",
            "name": "security-analyst",
            "type": "user",
            "mfa_enabled": 1,
            "access_key_age_days": 18,
            "last_activity": "2026-06-10T08:30:00+00:00",
            "risk_score": 0,
            "updated_at": db.utc_now(),
        },
        {
            "id": "demo:user/automation-bot",
            "name": "automation-bot",
            "type": "user",
            "mfa_enabled": 0,
            "access_key_age_days": 126,
            "last_activity": "2026-06-10T04:10:00+00:00",
            "risk_score": 0,
            "updated_at": db.utc_now(),
        },
        {
            "id": "demo:role/reporting-admin",
            "name": "reporting-admin",
            "type": "role",
            "mfa_enabled": 1,
            "access_key_age_days": None,
            "last_activity": "2026-06-10T07:45:00+00:00",
            "risk_score": 0,
            "updated_at": db.utc_now(),
        },
    ]
    for identity in identities:
        db.upsert_identity(identity)

    events = [
        event_payload(0, "ConsoleLogin", "demo:user/security-analyst", "IAMUser", "198.51.100.25", mfa="Yes"),
        event_payload(1, "AttachRolePolicy", "demo:role/reporting-admin", "AssumedRole", "198.51.100.25"),
        event_payload(2, "ConsoleLogin", "demo:user/automation-bot", "IAMUser", "203.0.113.17", mfa="No"),
        event_payload(3, "CreatePolicy", "demo:user/automation-bot", "IAMUser", "203.0.113.17"),
        event_payload(4, "ListBuckets", "demo:user/security-analyst", "IAMUser", "198.51.100.25"),
        event_payload(5, "GetObject", "demo:user/automation-bot", "IAMUser", "203.0.113.17", error_code="AccessDenied"),
        event_payload(6, "PutUserPolicy", "demo:user/automation-bot", "IAMUser", "203.0.113.17", error_code="AccessDenied"),
        event_payload(7, "DeleteBucket", "demo:role/reporting-admin", "AssumedRole", "198.51.100.25"),
        event_payload(8, "DescribeInstances", "demo:user/security-analyst", "IAMUser", "198.51.100.25"),
        event_payload(9, "GetCredentialReport", "demo:user/security-analyst", "IAMUser", "198.51.100.25"),
    ]
    for item in events:
        db.upsert_event(item)

    db.upsert_finding(
        {
            "id": "demo-finding-001",
            "resource_type": "AWS::S3::Bucket",
            "resource_arn": "demo:resource/reports-archive",
            "status": "ACTIVE",
            "severity": "HIGH",
            "created_at": "2026-06-10T06:00:00+00:00",
            "updated_at": "2026-06-10T08:00:00+00:00",
            "raw": json.dumps({"id": "demo-finding-001", "note": "sanitized demo finding"}),
        }
    )

    run_detection()
    recalculate_risk_scores()

    if sample_report:
        sample_report.parent.mkdir(parents=True, exist_ok=True)
        report = generate_pdf_report("2026-06-10T00:00:00+00:00", "2026-06-10T23:59:59+00:00")
        Path(report["file_path"]).replace(sample_report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sanitized demo data for screenshots and portfolio assets.")
    parser.add_argument("--database", default=str(ROOT / "backend" / "data" / "demo.sqlite3"))
    parser.add_argument("--report-dir", default=str(ROOT / "backend" / "reports" / "out"))
    parser.add_argument("--sample-report", default=str(ROOT / "docs" / "sample_report.pdf"))
    args = parser.parse_args()

    os.environ["DATABASE_PATH"] = args.database
    os.environ["REPORT_DIR"] = args.report_dir
    seed(Path(args.database), Path(args.report_dir), Path(args.sample_report) if args.sample_report else None)
    print(f"Seeded sanitized demo database: {args.database}")
    if args.sample_report:
        print(f"Wrote sanitized sample report: {args.sample_report}")


if __name__ == "__main__":
    main()

