import json

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.storage import db


def test_api_smoke(tmp_path):
    object.__setattr__(settings, "database_path", tmp_path / "api.sqlite3")
    object.__setattr__(settings, "report_dir", tmp_path / "reports")
    db.init_db()
    db.upsert_event(
        {
            "id": "evt-api",
            "event_time": "2026-06-10T00:00:00+00:00",
            "event_name": "ConsoleLogin",
            "user_identity": json.dumps({"type": "Root", "arn": "arn:aws:iam::123456789012:root"}),
            "subject": "arn:aws:iam::123456789012:root",
            "source_ip": "198.51.100.1",
            "aws_region": "ap-south-1",
            "error_code": None,
            "raw": json.dumps({"userIdentity": {"type": "Root"}, "eventName": "ConsoleLogin"}),
            "ingested_at": db.utc_now(),
        }
    )

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/events").json()[0]["id"] == "evt-api"
    assert client.get("/events/summary").json()["total"] == 1
    report_response = client.post("/reports/generate", json={"report_type": "CSV"})
    assert report_response.status_code == 200
    assert client.get(f"/reports/download/{report_response.json()['id']}").status_code == 200

