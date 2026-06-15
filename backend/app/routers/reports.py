from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.reports.csv_export import generate_csv_report
from app.reports.pdf_generator import generate_pdf_report
from app.storage import db

router = APIRouter()


class ReportRequest(BaseModel):
    report_type: str = "PDF"
    time_range_start: str | None = None
    time_range_end: str | None = None


@router.post("/reports/generate")
def generate_report(request: ReportRequest):
    report_type = request.report_type.upper()
    if report_type == "PDF":
        return generate_pdf_report(request.time_range_start, request.time_range_end)
    if report_type == "CSV":
        return generate_csv_report(request.time_range_start, request.time_range_end)
    raise HTTPException(status_code=400, detail="report_type must be PDF or CSV")


@router.get("/reports")
def reports():
    return db.list_rows("reports", limit=100)


@router.get("/reports/download/{report_id}")
def download_report(report_id: str):
    report = db.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="report not found")
    return FileResponse(report["file_path"], filename=report["file_path"].split("\\")[-1].split("/")[-1])

