from fastapi import APIRouter

from app.config import settings
from app.storage import db

router = APIRouter()


@router.get("/health")
def health():
    db.init_db()
    return {"status": "ok", "region": settings.aws_region}

