from fastapi import APIRouter, Query

from app.storage import db

router = APIRouter()


@router.get("/events")
def events(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    subject: str | None = None,
    event_name: str | None = None,
    error_code: str | None = None,
):
    return db.list_rows("events", limit=limit, offset=offset, filters={"subject": subject, "event_name": event_name, "error_code": error_code})


@router.get("/events/summary")
def events_summary():
    rows = db.list_rows("events", limit=5000)
    by_event: dict[str, int] = {}
    by_subject: dict[str, int] = {}
    by_hour: dict[str, int] = {}
    for row in rows:
        by_event[row["event_name"]] = by_event.get(row["event_name"], 0) + 1
        by_subject[row["subject"]] = by_subject.get(row["subject"], 0) + 1
        hour = row["event_time"][:13]
        by_hour[hour] = by_hour.get(hour, 0) + 1
    return {"total": len(rows), "by_event": by_event, "by_subject": by_subject, "by_hour": by_hour}

