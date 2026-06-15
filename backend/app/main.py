from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import anomalies, events, findings, health, identities, ingest, reports
from app.scheduler.jobs import create_scheduler
from app.storage.db import init_db


app = FastAPI(title="Data Protection Reporting Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(anomalies.router)
app.include_router(identities.router)
app.include_router(findings.router)
app.include_router(ingest.router)
app.include_router(reports.router)

_scheduler = None


@app.on_event("startup")
def startup() -> None:
    global _scheduler
    init_db()
    if settings.enable_scheduler and _scheduler is None:
        _scheduler = create_scheduler()
        _scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if _scheduler:
        _scheduler.shutdown(wait=False)

