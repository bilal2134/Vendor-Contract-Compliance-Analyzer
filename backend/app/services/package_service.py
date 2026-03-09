from __future__ import annotations

from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk, Job, Report, ReviewerNote, VendorPackage
from app.schemas.common import DocumentType, JobStage
from app.services.chunking import chunk_pages, extract_keywords
from app.services.compliance_engine import build_report
from app.services.playbook_service import get_playbook
from app.services.storage import persist_upload
from app.services.text_extraction import extract_text_pages
from app.services.vector_store import vector_store


async def ingest_vendor_package(
    db: Session,
    *,
    vendor_name: str,
    playbook_version_id: str,
    uploads: dict[str, UploadFile],
) -> dict:
    playbook = get_playbook(db, playbook_version_id)
    if playbook is None:
        raise ValueError("A playbook must be uploaded before vendor package analysis can run.")

    package_id = f"pkg_{uuid4().hex[:12]}"
    job_id = f"job_{uuid4().hex[:12]}"
    report_id = f"rpt_{uuid4().hex[:12]}"

    package = VendorPackage(
        id=package_id,
        vendor_name=vendor_name,
        playbook_version_id=playbook.id,
        status=JobStage.COMPLETE.value,
    )
    job = Job(
        id=job_id,
        job_type="package_analysis",
        target_id=package_id,
        status=JobStage.COMPLETE.value,
        progress=100,
        current_step="Package parsed, indexed, and analyzed.",
        warnings_json=[],
    )
    db.add(package)
    db.add(job)
    db.flush()

    chunk_records: list[DocumentChunk] = []
    warnings: list[str] = []
    for document_type, upload in uploads.items():
        stored_path = await persist_upload(upload, _package_storage_dir(package_id, document_type))
        pages = extract_text_pages(stored_path)
        combined_text = "\n\n".join(page["text"] for page in pages)
        if not combined_text:
            warnings.append(f"{upload.filename} produced no extractable text.")
        document = Document(
            id=f"doc_{uuid4().hex[:12]}",
            owner_type="package",
            owner_id=package_id,
            document_type=document_type,
            filename=upload.filename or stored_path.name,
            source_path=str(stored_path),
            content_type=upload.content_type,
            text_content=combined_text,
            page_count=len(pages),
            metadata_json={"document_type": document_type, "keywords": extract_keywords(combined_text)},
        )
        db.add(document)
        db.flush()
        for chunk in chunk_pages(pages):
            chunk_records.append(
                DocumentChunk(
                    id=f"chk_{uuid4().hex[:12]}",
                    document_id=document.id,
                    owner_type="package",
                    owner_id=package_id,
                    document_type=document_type,
                    chunk_index=chunk["chunk_index"],
                    page_number=chunk["page_number"],
                    section_name=chunk["section_name"],
                    text=chunk["text"],
                    keywords_json=chunk["keywords"],
                    metadata_json={"section_name": chunk["section_name"]},
                )
            )
    db.add_all(chunk_records)
    db.flush()
    vector_store.upsert_chunks(
        owner_type="vendor",
        items=[
            {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": {
                    "chunk_id": chunk.id,
                    "owner_id": package_id,
                    "page_number": chunk.page_number,
                    "document_type": chunk.document_type,
                },
            }
            for chunk in chunk_records
        ],
    )

    report_payload = build_report(db, package, playbook.id)
    report = Report(
        id=report_id,
        package_id=package.id,
        playbook_version_id=playbook.id,
        vendor_name=vendor_name,
        summary_json=report_payload["summary"],
        findings_json=report_payload["findings"],
        conflicts_json=report_payload["conflicts"],
    )
    job.warnings_json = warnings
    db.add(report)
    db.commit()
    return {"job": job, "package": package, "report": report}


def list_reports(db: Session) -> list[Report]:
    return db.scalars(select(Report).order_by(desc(Report.created_at))).all()


def get_report(db: Session, report_id: str) -> Report | None:
    return db.get(Report, report_id)


def add_reviewer_note(db: Session, finding_id: str, note: str, override_status: str | None) -> ReviewerNote:
    entry = ReviewerNote(finding_id=finding_id, note=note, override_status=override_status)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_reviewer_notes(db: Session, finding_id: str) -> list[ReviewerNote]:
    return db.scalars(select(ReviewerNote).where(ReviewerNote.finding_id == finding_id).order_by(desc(ReviewerNote.created_at))).all()


def get_job(db: Session, job_id: str) -> Job | None:
    return db.get(Job, job_id)


def _package_storage_dir(package_id: str, document_type: str):
    from app.core.settings import get_settings

    settings = get_settings()
    return settings.storage_root / "packages" / package_id / document_type
