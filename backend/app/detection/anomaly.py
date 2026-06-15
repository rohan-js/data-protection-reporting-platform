from __future__ import annotations

import ipaddress
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.detection.rules import PRIVILEGE_ESCALATION_EVENTS, SENSITIVE_EVENTS
from app.storage import db


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _network_prefix(ip_value: str | None) -> str | None:
    if not ip_value:
        return None
    try:
        ip = ipaddress.ip_address(ip_value)
    except ValueError:
        return None
    if ip.is_private or ip.is_loopback or ip.is_reserved:
        return None
    if ip.version == 4:
        return str(ipaddress.ip_network(f"{ip}/24", strict=False))
    return str(ipaddress.ip_network(f"{ip}/64", strict=False))


def _anomaly(event_id: str | None, anomaly_type: str, severity: str, subject: str, description: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "anomaly_type": anomaly_type,
        "severity": severity,
        "subject": subject or "unknown",
        "description": description,
        "detected_at": db.utc_now(),
    }


def detect_event_anomalies(events: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    events = events or db.get_event_rows()
    anomalies: list[dict[str, Any]] = []
    denied_by_subject: dict[str, list[datetime]] = defaultdict(list)
    prefixes_by_subject: dict[str, set[str]] = defaultdict(set)

    for event in sorted(events, key=lambda item: item["event_time"]):
        raw = db.decode_json(event["raw"]) or {}
        identity = db.decode_json(event.get("user_identity")) or raw.get("userIdentity") or {}
        subject = event.get("subject") or identity.get("arn") or "unknown"
        event_name = event.get("event_name")
        event_id = event.get("id")

        if identity.get("type") == "Root":
            anomalies.append(_anomaly(event_id, "ROOT_USAGE", "CRITICAL", subject, "Root account activity was observed."))

        if event_name == "ConsoleLogin" and (raw.get("additionalEventData") or {}).get("MFAUsed") == "No":
            anomalies.append(_anomaly(event_id, "CONSOLE_LOGIN_WITHOUT_MFA", "HIGH", subject, "Console login completed without MFA."))

        if event_name in PRIVILEGE_ESCALATION_EVENTS and not event.get("error_code"):
            anomalies.append(_anomaly(event_id, "IAM_PRIVILEGE_ESCALATION", "HIGH", subject, f"Sensitive IAM change succeeded: {event_name}."))

        if event.get("error_code") and "AccessDenied" in event["error_code"]:
            denied_by_subject[subject].append(_parse_time(event["event_time"]))

        event_time = _parse_time(event["event_time"])
        if event_name in SENSITIVE_EVENTS and (event_time.hour < 6 or event_time.hour >= 22):
            anomalies.append(_anomaly(event_id, "SENSITIVE_API_OFF_HOURS", "MEDIUM", subject, f"Sensitive API {event_name} ran outside business hours."))

        prefix = _network_prefix(event.get("source_ip"))
        if prefix:
            known = prefixes_by_subject[subject]
            if len(known) >= 2 and prefix not in known:
                anomalies.append(_anomaly(event_id, "UNUSUAL_GEO_ACCESS", "HIGH", subject, f"New public network prefix observed: {prefix}."))
            known.add(prefix)

    for subject, times in denied_by_subject.items():
        times.sort()
        for index, start in enumerate(times):
            window = [item for item in times[index:] if (item - start).total_seconds() <= 600]
            if len(window) >= 5:
                anomalies.append(_anomaly(None, "DENIED_API_SPIKE", "MEDIUM", subject, "Five or more AccessDenied events occurred within 10 minutes."))
                break

    return anomalies


def detect_credential_anomalies() -> list[dict[str, Any]]:
    anomalies = []
    for identity in db.list_rows("iam_identities", limit=1000):
        if identity["type"] == "user" and not identity["mfa_enabled"]:
            anomalies.append(_anomaly(None, "MFA_MISSING", "HIGH", identity["id"], "IAM user does not have MFA enabled."))
        age = identity.get("access_key_age_days")
        if age is not None and age > 90:
            anomalies.append(_anomaly(None, "ACCESS_KEY_AGE_VIOLATION", "MEDIUM", identity["id"], f"Access key age is {age} days."))
    return anomalies


def detect_finding_anomalies() -> list[dict[str, Any]]:
    anomalies = []
    for finding in db.get_finding_rows():
        if finding["status"] == "ACTIVE":
            anomalies.append(
                _anomaly(
                    finding["id"],
                    "PUBLIC_RESOURCE_EXPOSURE",
                    finding["severity"],
                    finding["resource_arn"],
                    f"Access Analyzer reports active external access for {finding['resource_type']}.",
                )
            )
    return anomalies


def run_detection() -> int:
    anomalies = detect_event_anomalies()
    anomalies.extend(detect_credential_anomalies())
    anomalies.extend(detect_finding_anomalies())
    return db.insert_anomalies(anomalies)


def summary() -> dict[str, Any]:
    rows = db.list_rows("anomalies", limit=1000)
    by_severity = Counter(row["severity"] for row in rows if not row["acknowledged"])
    by_type = Counter(row["anomaly_type"] for row in rows if not row["acknowledged"])
    return {"total_open": sum(by_severity.values()), "by_severity": dict(by_severity), "by_type": dict(by_type)}

