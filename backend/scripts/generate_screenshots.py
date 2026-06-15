from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "screenshots"

W = 1600
H = 1000
BG = "#f5f7f8"
PANEL = "#ffffff"
TEXT = "#172026"
MUTED = "#60717b"
SIDEBAR = "#172026"
ACCENT = "#2f6f73"
ACCENT_2 = "#c06014"
ACCENT_3 = "#a7343f"
LINE = "#d8e0e4"


def font(size: int, bold: bool = False):
    paths = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    if bold:
        paths = [p.replace(".ttf", "bd.ttf") if p.endswith("segoeui.ttf") else p for p in paths]
    for path in paths:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_text(draw, xy, text, *, size=22, fill=TEXT, bold=False, max_width=None):
    f = font(size, bold=bold)
    if max_width:
        text = fit_text(draw, text, f, max_width)
    draw.text(xy, text, font=f, fill=fill)
    return draw.textbbox(xy, text, font=f)


def fit_text(draw, text, fnt, max_width):
    if draw.textlength(text, font=fnt) <= max_width:
        return text
    for length in range(len(text), 0, -1):
        candidate = text[:length].rstrip() + "..."
        if draw.textlength(candidate, font=fnt) <= max_width:
            return candidate
    return "..."


def rounded(draw, box, radius=16, fill=PANEL, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def header(draw, title, subtitle):
    draw.rectangle((0, 0, W, 96), fill=PANEL)
    draw_text(draw, (48, 28), title, size=30, bold=True)
    draw_text(draw, (48, 62), subtitle, size=16, fill=MUTED)
    draw.rectangle((0, 96, W, 97), fill=LINE)


def sidebar(draw, active="dashboard"):
    draw.rectangle((0, 0, 240, H), fill=SIDEBAR)
    draw_text(draw, (34, 32), "Data Protection", size=24, fill="#ffffff", bold=True)
    draw_text(draw, (34, 62), "Reporting Platform", size=17, fill="#a7b4be")
    items = ["dashboard", "events", "anomalies", "identities", "findings", "reports"]
    y = 160
    for item in items:
        if item == active:
            rounded(draw, (20, y - 8, 220, y + 34), radius=10, fill="#2f6f73")
        draw_text(draw, (40, y), item, size=20, fill="#ffffff", bold=item == active)
        y += 58


def kpi_card(draw, x, y, w, h, title, value, color):
    rounded(draw, (x, y, x + w, y + h), radius=14)
    draw.ellipse((x + 18, y + 18, x + 62, y + 62), fill=color)
    draw_text(draw, (x + 82, y + 22), title, size=15, fill=MUTED)
    draw_text(draw, (x + 82, y + 40), str(value), size=30, bold=True)


def chart_panel(draw, x, y, w, h, title, bars):
    rounded(draw, (x, y, x + w, y + h), radius=14)
    draw_text(draw, (x + 24, y + 20), title, size=22, bold=True)
    left = x + 42
    bottom = y + h - 46
    top = y + 78
    chart_w = w - 84
    chart_h = bottom - top
    maxv = max(bars) if bars else 1
    bar_w = chart_w // len(bars) - 6
    for i, val in enumerate(bars):
        bx = left + i * (chart_w // len(bars))
        bh = int(chart_h * val / maxv)
        draw.rounded_rectangle((bx, bottom - bh, bx + bar_w, bottom), radius=6, fill=ACCENT)
    for i in range(0, maxv + 1, max(1, math.ceil(maxv / 4))):
        ty = bottom - int(chart_h * i / maxv)
        draw.line((left, ty, left + chart_w, ty), fill="#eef2f4", width=1)
        draw_text(draw, (x + 10, ty - 8), str(i), size=14, fill=MUTED)


def table_panel(draw, x, y, w, h, title, columns, rows, *, highlight_col=None):
    rounded(draw, (x, y, x + w, y + h), radius=14)
    draw_text(draw, (x + 24, y + 20), title, size=22, bold=True)
    top = y + 66
    col_widths = columns.get("widths") or [int((w - 48) / len(columns["headers"]))] * len(columns["headers"])
    cx = x + 24
    for idx, header_text in enumerate(columns["headers"]):
        draw_text(draw, (cx, top), header_text, size=14, fill=MUTED, bold=True, max_width=col_widths[idx] - 12)
        cx += col_widths[idx]
    y0 = top + 26
    row_h = (h - 100) // max(1, len(rows))
    row_h = max(42, row_h)
    for r, row in enumerate(rows):
        yy = y0 + r * row_h
        draw.line((x + 20, yy - 6, x + w - 20, yy - 6), fill="#edf1f3", width=1)
        cx = x + 24
        for idx, cell in enumerate(row):
            fill = ACCENT_3 if highlight_col == idx and str(cell).upper() in {"CRITICAL", "HIGH"} else TEXT
            draw_text(draw, (cx, yy), str(cell), size=15, fill=fill, bold=idx == 0, max_width=col_widths[idx] - 12)
            cx += col_widths[idx]


def anomaly_feed(draw, x, y, w, h, title, items):
    rounded(draw, (x, y, x + w, y + h), radius=14)
    draw_text(draw, (x + 24, y + 20), title, size=22, bold=True)
    yy = y + 68
    colors = {"CRITICAL": ACCENT_3, "HIGH": ACCENT_2, "MEDIUM": "#b48a1f", "LOW": ACCENT}
    for sev, kind, subject in items:
        rounded(draw, (x + 20, yy, x + w - 20, yy + 88), radius=12, outline=LINE)
        draw.rectangle((x + 20, yy, x + 26, yy + 88), fill=colors.get(sev, ACCENT))
        draw_text(draw, (x + 40, yy + 12), sev, size=14, fill=colors.get(sev, ACCENT), bold=True)
        draw_text(draw, (x + 100, yy + 12), kind, size=16, bold=True)
        draw_text(draw, (x + 40, yy + 42), subject, size=14, fill=MUTED)
        yy += 100


def report_cards(draw, x, y, w, h):
    rounded(draw, (x, y, x + w, y + h), radius=14)
    draw_text(draw, (x + 24, y + 20), "Reports", size=22, bold=True)
    cards = [
        ("PDF report", "Executive summary + anomalies + risk table", ACCENT),
        ("CSV export", "Filtered anomaly feed for spreadsheet review", ACCENT_2),
        ("Sample PDF", "docs/sample_report.pdf is committed safely", ACCENT_3),
    ]
    cy = y + 72
    for title, desc, color in cards:
        rounded(draw, (x + 20, cy, x + w - 20, cy + 110), radius=12, outline=LINE)
        draw.ellipse((x + 36, cy + 24, x + 70, cy + 58), fill=color)
        draw_text(draw, (x + 90, cy + 18), title, size=18, bold=True)
        draw_text(draw, (x + 90, cy + 46), desc, size=14, fill=MUTED)
        cy += 128


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / name)


def dashboard():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    sidebar(draw, "dashboard")
    header(draw, "Cloud Identity Reporting", "Sanitized demo data for portfolio screenshots")
    kpi_card(draw, 268, 132, 290, 112, "Total Events", 82, ACCENT)
    kpi_card(draw, 578, 132, 290, 112, "Open Anomalies", 33, ACCENT_2)
    kpi_card(draw, 888, 132, 290, 112, "High-Risk Identities", 1, ACCENT_3)
    kpi_card(draw, 1198, 132, 290, 112, "Active Findings", 1, "#3b82f6")
    chart_panel(draw, 268, 272, 700, 310, "Activity by Hour", [2, 5, 7, 4, 9, 11, 8, 14, 17, 13, 9, 6])
    anomaly_feed(draw, 990, 272, 498, 546, "Recent Anomalies", [
        ("CRITICAL", "ROOT_USAGE", "demo:root"),
        ("HIGH", "CONSOLE_LOGIN_WITHOUT_MFA", "demo:user/automation-bot"),
        ("HIGH", "IAM_PRIVILEGE_ESCALATION", "demo:role/reporting-admin"),
        ("MEDIUM", "ACCESS_KEY_AGE_VIOLATION", "demo:user/automation-bot"),
    ])
    table_panel(
        draw,
        268,
        612,
        700,
        206,
        "IAM Risk Rankings",
        {"headers": ["Identity", "Type", "Risk", "MFA"], "widths": [300, 130, 110, 80]},
        [
            ["demo:user/automation-bot", "user", "24", "no"],
            ["demo:user/security-analyst", "user", "6", "yes"],
            ["demo:role/reporting-admin", "role", "2", "yes"],
        ],
    )
    report_cards(draw, 990, 878, 498, 112)
    save(img, "dashboard.png")


def events():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    sidebar(draw, "events")
    header(draw, "CloudTrail Events", "Sanitized demo event history and filters")
    rounded(draw, (268, 132, 1490, 206), radius=14)
    draw_text(draw, (292, 156), "Filters", size=20, bold=True)
    for i, label in enumerate(["User", "Event name", "Time range", "Error code"]):
        x = 390 + i * 258
        rounded(draw, (x, 148, x + 220, 188), radius=10, outline=LINE)
        draw_text(draw, (x + 14, 159), label, size=14, fill=MUTED)
    table_panel(
        draw,
        268,
        228,
        1222,
        664,
        "Event Explorer",
        {"headers": ["Time", "Event", "Identity", "Source IP", "Error"], "widths": [270, 200, 340, 190, 150]},
        [
            ["2026-06-10 09:00", "ConsoleLogin", "demo:user/security-analyst", "198.51.100.25", "-"],
            ["2026-06-10 08:00", "AttachRolePolicy", "demo:role/reporting-admin", "198.51.100.25", "-"],
            ["2026-06-10 07:00", "ConsoleLogin", "demo:user/automation-bot", "203.0.113.17", "-"],
            ["2026-06-10 06:00", "CreatePolicy", "demo:user/automation-bot", "203.0.113.17", "-"],
            ["2026-06-10 05:00", "GetObject", "demo:user/automation-bot", "203.0.113.17", "AccessDenied"],
        ],
    )
    save(img, "events.png")


def anomalies():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    sidebar(draw, "anomalies")
    header(draw, "Anomalies", "Rule-based findings with severity and subject identity")
    table_panel(
        draw,
        268,
        132,
        1222,
        770,
        "Anomaly Feed",
        {"headers": ["Severity", "Rule", "Subject", "Detected"], "widths": [150, 320, 460, 230]},
        [
            ["CRITICAL", "ROOT_USAGE", "demo:root", "2026-06-10 09:00"],
            ["HIGH", "CONSOLE_LOGIN_WITHOUT_MFA", "demo:user/automation-bot", "2026-06-10 07:00"],
            ["HIGH", "IAM_PRIVILEGE_ESCALATION", "demo:role/reporting-admin", "2026-06-10 08:00"],
            ["MEDIUM", "ACCESS_KEY_AGE_VIOLATION", "demo:user/automation-bot", "2026-06-10 06:00"],
            ["MEDIUM", "ACCESS_KEY_AGE_VIOLATION", "demo:user/automation-bot", "2026-06-10 05:00"],
        ],
        highlight_col=0,
    )
    save(img, "anomalies.png")


def identities():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    sidebar(draw, "identities")
    header(draw, "IAM Risk Rankings", "Sanitized risk summary without real account identifiers")
    table_panel(
        draw,
        268,
        132,
        1222,
        770,
        "Identity Risk Table",
        {"headers": ["Identity", "Type", "MFA", "Key age", "Risk"], "widths": [420, 130, 120, 170, 120]},
        [
            ["demo:user/automation-bot", "user", "no", "126 days", "24"],
            ["demo:user/security-analyst", "user", "yes", "18 days", "6"],
            ["demo:role/reporting-admin", "role", "yes", "-", "2"],
        ],
    )
    save(img, "identities.png")


def reports():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    sidebar(draw, "reports")
    header(draw, "Reports", "PDF and CSV exports generated from sanitized demo data")
    report_cards(draw, 268, 132, 560, 770)
    table_panel(
        draw,
        852,
        132,
        638,
        770,
        "Generated Reports",
        {"headers": ["Generated", "Type", "ID"], "widths": [250, 110, 240]},
        [
            ["2026-06-10 09:15", "PDF", "3a0309f7-839c-4e0e-803a-25b32a06c59a"],
            ["2026-06-10 09:20", "CSV", "88820c25-254c-40af-b7aa-775fad987877"],
            ["2026-06-10 09:22", "PDF", "a986967e-d38b-43a3-b691-fc2e6c854690"],
        ],
    )
    save(img, "reports.png")


def main():
    dashboard()
    events()
    anomalies()
    identities()
    reports()
    print(f"Generated screenshots in {OUT}")


if __name__ == "__main__":
    main()

