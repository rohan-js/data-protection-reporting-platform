from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.detection.anomaly import run_detection
from app.detection.scoring import recalculate_risk_scores
from app.ingestion.access_analyzer import ingest_findings
from app.ingestion.cloudtrail import ingest_cloudtrail
from app.ingestion.iam_report import ingest_credential_report


def run_full_ingestion() -> dict[str, int]:
    results = {
        "events": ingest_cloudtrail(),
        "credentials": ingest_credential_report(),
        "findings": ingest_findings(),
    }
    results["anomalies"] = run_detection()
    results["identities_scored"] = recalculate_risk_scores()
    return results


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(lambda: ingest_cloudtrail(), "interval", hours=6, id="cloudtrail")
    scheduler.add_job(lambda: ingest_credential_report(), "interval", hours=24, id="credential-report")
    scheduler.add_job(lambda: ingest_findings(), "interval", hours=24, id="access-analyzer")
    scheduler.add_job(lambda: (run_detection(), recalculate_risk_scores()), "interval", hours=6, id="detection")
    return scheduler

