from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

import boto3

from app.storage import db


def _parse_date(value: str | None) -> datetime | None:
    if not value or value in {"N/A", "no_information", "not_supported"}:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_days(value: str | None) -> int | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return max(0, (datetime.now(timezone.utc) - parsed).days)


def parse_credential_report(content: bytes) -> list[dict[str, Any]]:
    rows = csv.DictReader(io.StringIO(content.decode("utf-8")))
    identities = []
    for row in rows:
        user = row["user"]
        if user == "<root_account>":
            arn = "arn:aws:iam::root"
            identity_type = "root"
        else:
            arn = row.get("arn") or user
            identity_type = "user"
        key_ages = [
            age for age in (
                _age_days(row.get("access_key_1_last_rotated")),
                _age_days(row.get("access_key_2_last_rotated")),
            )
            if age is not None
        ]
        identities.append(
            {
                "id": arn,
                "name": user,
                "type": identity_type,
                "mfa_enabled": 1 if row.get("mfa_active", "").lower() == "true" else 0,
                "access_key_age_days": max(key_ages) if key_ages else None,
                "last_activity": row.get("password_last_used") if row.get("password_last_used") not in {"N/A", "no_information"} else None,
                "risk_score": 0,
                "updated_at": db.utc_now(),
            }
        )
    return identities


def ingest_credential_report(client: Any | None = None) -> int:
    client = client or boto3.client("iam")
    client.generate_credential_report()
    response = client.get_credential_report()
    identities = parse_credential_report(response["Content"])
    for identity in identities:
        db.upsert_identity(identity)
    return len(identities)

