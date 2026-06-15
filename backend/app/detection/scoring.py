from __future__ import annotations

from collections import Counter, defaultdict

from app.storage import db


def recalculate_risk_scores() -> int:
    anomalies = db.list_rows("anomalies", limit=5000)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for anomaly in anomalies:
        counts[anomaly["subject"]][anomaly["anomaly_type"]] += 1

    updated = 0
    for identity in db.list_rows("iam_identities", limit=1000):
        subject_counts = counts.get(identity["id"], Counter())
        score = 0
        score += min(40, subject_counts["ROOT_USAGE"] * 40)
        score += 20 if not identity["mfa_enabled"] and identity["type"] == "user" else 0
        key_age = identity.get("access_key_age_days") or 0
        score += min(15, int(key_age / 365 * 15))
        score += min(10, subject_counts["DENIED_API_SPIKE"] * 10)
        score += min(10, subject_counts["SENSITIVE_API_OFF_HOURS"] * 10)
        score += min(5, subject_counts["PUBLIC_RESOURCE_EXPOSURE"] * 5)
        identity["risk_score"] = min(100, score)
        identity["updated_at"] = db.utc_now()
        db.upsert_identity(identity)
        updated += 1
    return updated

