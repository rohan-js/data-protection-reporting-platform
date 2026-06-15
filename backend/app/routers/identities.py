from fastapi import APIRouter, Query

from app.storage import db

router = APIRouter()


@router.get("/identities/risk")
@router.get("/roles/risk")
def identities(limit: int = Query(100, ge=1, le=500), identity_type: str | None = None):
    rows = db.list_rows("iam_identities", limit=limit, filters={"type": identity_type})
    return sorted(rows, key=lambda item: item["risk_score"], reverse=True)


@router.get("/credentials")
def credentials():
    return db.list_rows("iam_identities", limit=500)

