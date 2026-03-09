from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import Report
from app.schemas.reporting import DashboardCard, DashboardResponse, PackageReport, ReviewerNoteEntry, ReviewerNoteRequest
from app.services.export_service import export_report
from app.services.package_service import add_reviewer_note, get_report, get_reviewer_notes, list_reports

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    cards = [
        DashboardCard(
            package_id=report.package_id,
            vendor_name=report.vendor_name,
            status="ready",
            critical_findings=report.summary_json.get("missing", 0) + report.summary_json.get("conflicts", 0),
            report_id=report.id,
        )
        for report in list_reports(db)
    ]
    return DashboardResponse(cards=cards)


@router.get("/{report_id}", response_model=PackageReport)
def get_package_report(report_id: str, db: Session = Depends(get_db)) -> PackageReport:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return PackageReport(
        report_id=report.id,
        package_id=report.package_id,
        vendor_name=report.vendor_name,
        playbook_version_id=report.playbook_version_id,
        summary=report.summary_json,
        findings=report.findings_json,
        conflicts=report.conflicts_json,
        created_at=report.created_at,
    )


@router.get("/{report_id}/export")
def export_package_report(
    report_id: str,
    export_format: str = Query("json", alias="format"),
    db: Session = Depends(get_db),
) -> Response:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    try:
        content, media_type = export_report(report, export_format)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return Response(content=content, media_type=media_type)


@router.post("/findings/{finding_id}/notes", status_code=status.HTTP_201_CREATED)
def create_reviewer_note(finding_id: str, payload: ReviewerNoteRequest, db: Session = Depends(get_db)) -> dict:
    entry = add_reviewer_note(
        db,
        finding_id=finding_id,
        note=payload.note,
        override_status=payload.override_status.value if payload.override_status else None,
    )
    return {
        "entry": ReviewerNoteEntry(
            finding_id=entry.finding_id,
            note=entry.note,
            override_status=entry.override_status,
            created_at=entry.created_at,
        )
    }


@router.get("/findings/{finding_id}/notes")
def list_reviewer_notes(finding_id: str, db: Session = Depends(get_db)) -> dict:
    entries = [
        ReviewerNoteEntry(
            finding_id=entry.finding_id,
            note=entry.note,
            override_status=entry.override_status,
            created_at=entry.created_at,
        )
        for entry in get_reviewer_notes(db, finding_id)
    ]
    return {"entries": entries}
