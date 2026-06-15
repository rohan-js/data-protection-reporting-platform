from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3

from app.config import settings
from app.storage import db


def _subject_from_identity(identity: dict[str, Any]) -> str:
    return (
        identity.get("arn")
        or identity.get("userName")
        or identity.get("principalId")
        or identity.get("type")
        or "unknown"
    )


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    raw = json.loads(event.get("CloudTrailEvent") or "{}")
    identity = raw.get("userIdentity") or {}
    event_time = event.get("EventTime") or raw.get("eventTime") or datetime.now(timezone.utc)
    if isinstance(event_time, datetime):
        event_time = event_time.astimezone(timezone.utc).isoformat()
    event_id = event.get("EventId") or raw.get("eventID")
    return {
        "id": event_id,
        "event_time": event_time,
        "event_name": event.get("EventName") or raw.get("eventName") or "Unknown",
        "user_identity": json.dumps(identity, default=str),
        "subject": _subject_from_identity(identity),
        "source_ip": raw.get("sourceIPAddress"),
        "aws_region": raw.get("awsRegion") or settings.aws_region,
        "error_code": raw.get("errorCode"),
        "raw": json.dumps(raw, default=str),
        "ingested_at": db.utc_now(),
    }


def ingest_cloudtrail(hours: int = 24, client: Any | None = None) -> int:
    client = client or boto3.client("cloudtrail", region_name=settings.aws_region)
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    next_token = None
    count = 0
    while True:
        kwargs: dict[str, Any] = {"StartTime": start_time, "MaxResults": 50}
        if next_token:
            kwargs["NextToken"] = next_token
        response = client.lookup_events(**kwargs)
        for event in response.get("Events", []):
            normalized = normalize_event(event)
            if normalized["id"]:
                db.upsert_event(normalized)
                count += 1
        next_token = response.get("NextToken")
        if not next_token:
            break
    return count

