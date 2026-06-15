from __future__ import annotations

import uuid

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import settings
from app.storage import db


def generate_pdf_report(start: str | None = None, end: str | None = None) -> dict[str, str]:
    settings.report_dir.mkdir(parents=True, exist_ok=True)
    report_id = str(uuid.uuid4())
    path = settings.report_dir / f"{report_id}.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=letter)
    styles = getSampleStyleSheet()
    anomalies = db.list_rows("anomalies", limit=200)
    identities = db.list_rows("iam_identities", limit=100)
    findings = db.list_rows("findings", limit=100)

    story = [
        Paragraph("Data Protection Report", styles["Title"]),
        Paragraph(f"Report period: {start or 'all available'} to {end or 'now'}", styles["Normal"]),
        Paragraph(f"Generated: {db.utc_now()}", styles["Normal"]),
        Spacer(1, 16),
        Paragraph("Executive Summary", styles["Heading2"]),
        Paragraph(
            f"{len(anomalies)} anomalies, {len(identities)} identities, and {len(findings)} external exposure findings are currently stored.",
            styles["Normal"],
        ),
        Spacer(1, 16),
    ]

    story.append(Paragraph("Anomaly Details", styles["Heading2"]))
    anomaly_table = [["Severity", "Type", "Subject", "Description"]]
    for item in anomalies[:40]:
        anomaly_table.append([item["severity"], item["anomaly_type"], item["subject"][:45], item["description"][:80]])
    story.append(_table(anomaly_table))
    story.append(Spacer(1, 16))

    story.append(Paragraph("IAM Risk Rankings", styles["Heading2"]))
    risk_table = [["Identity", "Type", "Risk", "MFA", "Key Age"]]
    for item in identities:
        risk_table.append([item["name"], item["type"], item["risk_score"], "yes" if item["mfa_enabled"] else "no", item.get("access_key_age_days") or ""])
    story.append(_table(risk_table))
    doc.build(story)

    report = {
        "id": report_id,
        "report_type": "PDF",
        "generated_at": db.utc_now(),
        "time_range_start": start,
        "time_range_end": end,
        "file_path": str(path),
    }
    db.save_report(report)
    return report


def _table(data: list[list[object]]) -> Table:
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243447")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table

