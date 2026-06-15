from fastapi import APIRouter, Query

from app.detection.anomaly import summary
from app.storage import db

router = APIRouter()


@router.get("/anomalies")
def anomalies(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), severity: str | None = None):
    return db.list_rows("anomalies", limit=limit, offset=offset, filters={"severity": severity})


@router.get("/anomalies/summary")
def anomalies_summary():
    return summary()

