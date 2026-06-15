from __future__ import annotations

import json
from typing import Any

import boto3

from app.config import settings
from app.storage import db


SEVERITY_BY_RESOURCE = {
    "AWS::S3::Bucket": "HIGH",
    "AWS::IAM::Role": "CRITICAL",
    "AWS::KMS::Key": "CRITICAL",
}


def _find_external_analyzer(client: Any) -> str | None:
    paginator = client.get_paginator("list_analyzers")
    for page in paginator.paginate(type="ACCOUNT"):
        for analyzer in page.get("analyzers", []):
            if analyzer.get("name") == settings.analyzer_name or analyzer.get("type") == "ACCOUNT":
                return analyzer["arn"]
    return None


def ingest_findings(client: Any | None = None) -> int:
    client = client or boto3.client("accessanalyzer", region_name=settings.aws_region)
    analyzer_arn = _find_external_analyzer(client)
    if not analyzer_arn:
        return 0
    count = 0
    paginator = client.get_paginator("list_findings")
    for page in paginator.paginate(analyzerArn=analyzer_arn):
        for finding in page.get("findings", []):
            resource_type = finding.get("resourceType", "UNKNOWN")
            normalized = {
                "id": finding["id"],
                "resource_type": resource_type,
                "resource_arn": finding.get("resource", "unknown"),
                "status": finding.get("status", "UNKNOWN"),
                "severity": SEVERITY_BY_RESOURCE.get(resource_type, "HIGH"),
                "created_at": str(finding.get("createdAt")) if finding.get("createdAt") else None,
                "updated_at": str(finding.get("updatedAt")) if finding.get("updatedAt") else None,
                "raw": json.dumps(finding, default=str),
            }
            db.upsert_finding(normalized)
            count += 1
    return count

