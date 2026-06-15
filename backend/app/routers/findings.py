from fastapi import APIRouter

from app.storage import db

router = APIRouter()


@router.get("/findings")
def findings():
    return db.list_rows("findings", limit=500)

