from fastapi import APIRouter, HTTPException

from app.scheduler.jobs import run_full_ingestion

router = APIRouter()


@router.post("/ingest")
def ingest():
    try:
        return run_full_ingestion()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

