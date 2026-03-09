from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.schemas.ingestion import (
    CreatePackageResponse,
    CreatePlaybookVersionResponse,
    JobStatusResponse,
    PlaybookListResponse,
    PlaybookSummary,
)
from app.core.database import get_db
from app.schemas.common import DocumentType
from app.services.package_service import get_job, ingest_vendor_package
from app.services.playbook_service import get_playbook, ingest_playbook, list_playbooks

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/playbooks", response_model=PlaybookListResponse)
def get_playbooks(db: Session = Depends(get_db)) -> PlaybookListResponse:
    items = [
        PlaybookSummary(
            version_id=playbook.id,
            name=playbook.name,
            effective_date=playbook.effective_date,
            description=playbook.description,
            requirement_count=playbook.requirement_count,
            status=playbook.status,
            created_at=playbook.created_at,
        )
        for playbook in list_playbooks(db)
    ]
    return PlaybookListResponse(items=items)


@router.post("/playbooks/upload", response_model=CreatePlaybookVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook_version(
    name: str = Form(...),
    effective_date: str = Form(...),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> CreatePlaybookVersionResponse:
    result = await ingest_playbook(db, name=name, effective_date=effective_date, description=description, upload=file)
    playbook = result["playbook"]
    return CreatePlaybookVersionResponse(
        version_id=playbook.id,
        status=result["job"].status,
        requirement_count=playbook.requirement_count,
        created_at=playbook.created_at,
    )


@router.post("/packages/upload", response_model=CreatePackageResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor_package(
    vendor_name: str = Form(...),
    playbook_version_id: str = Form("active"),
    msa: UploadFile = File(...),
    dpa: UploadFile | None = File(default=None),
    security: UploadFile | None = File(default=None),
    insurance: UploadFile | None = File(default=None),
    profile: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> CreatePackageResponse:
    if get_playbook(db, playbook_version_id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a playbook before analyzing packages.")
    uploads = {DocumentType.MSA.value: msa}
    if dpa is not None:
        uploads[DocumentType.DPA.value] = dpa
    if security is not None:
        uploads[DocumentType.SECURITY.value] = security
    if insurance is not None:
        uploads[DocumentType.INSURANCE.value] = insurance
    if profile is not None:
        uploads[DocumentType.PROFILE.value] = profile
    result = await ingest_vendor_package(
        db,
        vendor_name=vendor_name,
        playbook_version_id=playbook_version_id,
        uploads=uploads,
    )
    package_job = result["job"]
    return CreatePackageResponse(
        package_id=result["package"].id,
        job_id=package_job.id,
        report_id=result["report"].id,
        status=package_job.status,
        warnings=package_job.warnings_json,
        created_at=package_job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(
        job_id=job.id,
        package_id=job.target_id if job.job_type == "package_analysis" else None,
        playbook_version_id=job.target_id if job.job_type == "playbook_ingestion" else None,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        warnings=job.warnings_json,
        created_at=job.created_at,
    )
