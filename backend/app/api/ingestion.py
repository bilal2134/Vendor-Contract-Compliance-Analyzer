from fastapi import APIRouter, HTTPException, status

from app.schemas.ingestion import (
    CreatePackageRequest,
    CreatePackageResponse,
    CreatePlaybookVersionRequest,
    CreatePlaybookVersionResponse,
    JobStatusResponse,
)
from app.services.job_service import create_package_job, create_playbook_job, get_job

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/playbooks", response_model=CreatePlaybookVersionResponse, status_code=status.HTTP_201_CREATED)
def create_playbook_version(payload: CreatePlaybookVersionRequest) -> CreatePlaybookVersionResponse:
    result = create_playbook_job(payload)
    playbook = result["playbook"]
    return CreatePlaybookVersionResponse(
        version_id=playbook["version_id"],
        status=result["job"]["status"],
    )


@router.post("/packages", response_model=CreatePackageResponse, status_code=status.HTTP_201_CREATED)
def create_vendor_package(payload: CreatePackageRequest) -> CreatePackageResponse:
    result = create_package_job(payload)
    package_job = result["job"]
    return CreatePackageResponse(
        package_id=result["package"]["package_id"],
        job_id=package_job["job_id"],
        report_id=result["report"]["report_id"],
        status=package_job["status"],
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(**job)
