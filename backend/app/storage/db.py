from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import settings


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    event_time TEXT NOT NULL,
    event_name TEXT NOT NULL,
    user_identity TEXT,
    subject TEXT,
    source_ip TEXT,
    aws_region TEXT,
    error_code TEXT,
    raw TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    anomaly_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    UNIQUE(event_id, anomaly_type, subject)
);

CREATE TABLE IF NOT EXISTS iam_identities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    mfa_enabled INTEGER NOT NULL DEFAULT 0,
    access_key_age_days INTEGER,
    last_activity TEXT,
    risk_score INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL,
    resource_arn TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    raw TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    time_range_start TEXT,
    time_range_end TEXT,
    file_path TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(path: Path | None = None) -> None:
    db_path = path or settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(path: Path | None = None):
    init_db(path)
    conn = sqlite3.connect(path or settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def upsert_event(event: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO events
            (id, event_time, event_name, user_identity, subject, source_ip, aws_region, error_code, raw, ingested_at)
            VALUES (:id, :event_time, :event_name, :user_identity, :subject, :source_ip, :aws_region, :error_code, :raw, :ingested_at)
            """,
            event,
        )


def upsert_identity(identity: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO iam_identities
            (id, name, type, mfa_enabled, access_key_age_days, last_activity, risk_score, updated_at)
            VALUES (:id, :name, :type, :mfa_enabled, :access_key_age_days, :last_activity, :risk_score, :updated_at)
            """,
            identity,
        )


def upsert_finding(finding: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO findings
            (id, resource_type, resource_arn, status, severity, created_at, updated_at, raw)
            VALUES (:id, :resource_type, :resource_arn, :status, :severity, :created_at, :updated_at, :raw)
            """,
            finding,
        )


def insert_anomalies(anomalies: Iterable[dict[str, Any]]) -> int:
    inserted = 0
    with connect() as conn:
        for anomaly in anomalies:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO anomalies
                (event_id, anomaly_type, severity, subject, description, detected_at, acknowledged)
                VALUES (:event_id, :anomaly_type, :severity, :subject, :description, :detected_at, 0)
                """,
                anomaly,
            )
            inserted += cur.rowcount
    return inserted


def list_rows(table: str, limit: int = 100, offset: int = 0, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    allowed = {"events", "anomalies", "iam_identities", "findings", "reports"}
    if table not in allowed:
        raise ValueError(f"Unsupported table: {table}")
    filters = filters or {}
    clauses = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if key not in {"subject", "event_name", "error_code", "severity", "status", "type"}:
            continue
        clauses.append(f"{key} = :{key}")
        params[key] = value
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    order = "event_time DESC" if table == "events" else "updated_at DESC" if table in {"iam_identities", "findings"} else "id DESC"
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM {table} {where} ORDER BY {order} LIMIT :limit OFFSET :offset", params).fetchall()
    return [row_to_dict(row) for row in rows]


def get_event_rows() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM events ORDER BY event_time DESC").fetchall()
    return [row_to_dict(row) for row in rows]


def get_finding_rows() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM findings ORDER BY updated_at DESC").fetchall()
    return [row_to_dict(row) for row in rows]


def save_report(report: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reports
            (id, report_type, generated_at, time_range_start, time_range_end, file_path)
            VALUES (:id, :report_type, :generated_at, :time_range_start, :time_range_end, :file_path)
            """,
            report,
        )


def get_report(report_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return row_to_dict(row) if row else None


def decode_json(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value

