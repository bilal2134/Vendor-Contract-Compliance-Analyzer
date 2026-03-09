from fastapi import APIRouter, HTTPException, status

from app.schemas.reporting import DashboardResponse, PackageReport, ReviewerNoteRequest
from app.services.job_service import add_reviewer_note, get_report, get_reviewer_notes, list_dashboard_cards

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard() -> DashboardResponse:
    return DashboardResponse(cards=list_dashboard_cards())


@router.get("/{report_id}", response_model=PackageReport)
def get_package_report(report_id: str) -> PackageReport:
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return PackageReport(**report)


@router.post("/findings/{finding_id}/notes", status_code=status.HTTP_201_CREATED)
def create_reviewer_note(finding_id: str, payload: ReviewerNoteRequest) -> dict:
    return {
        "entry": add_reviewer_note(
            finding_id=finding_id,
            note=payload.note,
            override_status=payload.override_status.value if payload.override_status else None,
        )
    }


@router.get("/findings/{finding_id}/notes")
def list_reviewer_notes(finding_id: str) -> dict:
    return {"entries": get_reviewer_notes(finding_id)}
