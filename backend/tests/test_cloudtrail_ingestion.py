import json
from datetime import datetime, timezone

import boto3
from botocore.stub import ANY, Stubber

from app.ingestion.cloudtrail import ingest_cloudtrail, normalize_event


def test_normalize_event_extracts_identity_subject():
    raw = {
        "eventID": "evt-1",
        "eventName": "ConsoleLogin",
        "eventTime": "2026-06-10T01:00:00Z",
        "sourceIPAddress": "203.0.113.10",
        "awsRegion": "ap-south-1",
        "userIdentity": {"type": "IAMUser", "arn": "arn:aws:iam::123456789012:user/demo"},
    }
    normalized = normalize_event(
        {
            "EventId": "evt-1",
            "EventName": "ConsoleLogin",
            "EventTime": datetime(2026, 6, 10, tzinfo=timezone.utc),
            "CloudTrailEvent": json.dumps(raw),
        }
    )

    assert normalized["id"] == "evt-1"
    assert normalized["subject"] == "arn:aws:iam::123456789012:user/demo"
    assert normalized["event_name"] == "ConsoleLogin"


def test_ingest_cloudtrail_uses_lookup_events_stub(tmp_path, monkeypatch):
    from app.config import settings
    from app.storage import db

    object.__setattr__(settings, "database_path", tmp_path / "test.sqlite3")
    db.init_db()

    client = boto3.client(
        "cloudtrail",
        region_name="ap-south-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    stubber = Stubber(client)
    stubber.add_response(
        "lookup_events",
        {
            "Events": [
                {
                    "EventId": "evt-2",
                    "EventName": "CreateUser",
                    "EventTime": datetime(2026, 6, 10, tzinfo=timezone.utc),
                    "CloudTrailEvent": json.dumps(
                        {
                            "eventID": "evt-2",
                            "eventName": "CreateUser",
                            "eventTime": "2026-06-10T00:00:00Z",
                            "sourceIPAddress": "198.51.100.25",
                            "awsRegion": "ap-south-1",
                            "userIdentity": {"type": "IAMUser", "arn": "arn:aws:iam::123456789012:user/admin"},
                        }
                    ),
                }
            ]
        },
        {"StartTime": ANY, "MaxResults": 50},
    )

    with stubber:
        assert ingest_cloudtrail(client=client) == 1

    rows = db.list_rows("events")
    assert len(rows) == 1
    assert rows[0]["event_name"] == "CreateUser"

