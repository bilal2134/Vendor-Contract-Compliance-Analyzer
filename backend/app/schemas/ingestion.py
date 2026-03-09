from __future__ import annotations

from typing import List
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.common import DocumentType, JobStage, TimestampedModel


class VendorDocumentUpload(BaseModel):
    filename: str
    document_type: DocumentType = DocumentType.OTHER


class CreatePackageRequest(BaseModel):
    vendor_name: str = Field(min_length=2, max_length=200)
    playbook_version_id: str = Field(default="active")
    documents: List[VendorDocumentUpload] = Field(default_factory=list)


class CreatePackageResponse(TimestampedModel):
    package_id: str = Field(default_factory=lambda: f"pkg_{uuid4().hex[:12]}")
    job_id: str = Field(default_factory=lambda: f"job_{uuid4().hex[:12]}")
    report_id: str | None = None
    status: JobStage = JobStage.QUEUED


class CreatePlaybookVersionRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    effective_date: str
    description: str | None = None


class CreatePlaybookVersionResponse(TimestampedModel):
    version_id: str = Field(default_factory=lambda: f"pb_{uuid4().hex[:12]}")
    status: JobStage = JobStage.QUEUED


class JobStatusResponse(TimestampedModel):
    job_id: str
    package_id: str | None = None
    playbook_version_id: str | None = None
    status: JobStage
    progress: int = Field(ge=0, le=100)
    current_step: str
    warnings: list[str] = Field(default_factory=list)
