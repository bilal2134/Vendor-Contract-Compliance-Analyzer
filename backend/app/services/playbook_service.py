from __future__ import annotations

import re
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk, Job, PlaybookVersion, Requirement
from app.schemas.common import DocumentType, JobStage, Severity
from app.services.chunking import chunk_pages, extract_keywords, split_sentences
from app.services.storage import persist_upload
from app.services.text_extraction import extract_text_pages
from app.services.vector_store import vector_store

REQUIREMENT_RE = re.compile(r"\b(must|shall|required|minimum|at least|not exceed|maintain|include|reference)\b", re.IGNORECASE)


def _infer_category(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ["insurance", "liability", "coverage"]):
        return "Insurance & Risk"
    if any(token in lower for token in ["security", "soc 2", "iso 27001", "certification"]):
        return "Security Assurance"
    if any(token in lower for token in ["retention", "deletion", "data", "privacy"]):
        return "Data Governance"
    if any(token in lower for token in ["termination", "notice", "liability cap", "payment"]):
        return "Commercial Terms"
    return "General Compliance"


def _infer_expected_documents(text: str) -> list[str]:
    lower = text.lower()
    documents: list[str] = []
    mapping = {
        "msa": ["msa", "master service agreement"],
        "dpa": ["dpa", "data processing"],
        "security": ["security", "soc 2", "iso 27001", "questionnaire", "certification"],
        "insurance": ["insurance", "coverage", "liability"],
        "profile": ["profile", "reference", "company profile"],
    }
    for document_type, tokens in mapping.items():
        if any(token in lower for token in tokens):
            documents.append(document_type)
    return documents or [DocumentType.MSA.value, DocumentType.DPA.value, DocumentType.SECURITY.value, DocumentType.INSURANCE.value]


def _infer_severity(text: str) -> Severity:
    lower = text.lower()
    if any(token in lower for token in ["breach", "critical", "must not", "termination", "security incident"]):
        return Severity.CRITICAL
    if any(token in lower for token in ["insurance", "liability", "privacy", "retention"]):
        return Severity.HIGH
    if any(token in lower for token in ["reference", "certificate", "notice"]):
        return Severity.MEDIUM
    return Severity.LOW


def _extract_requirements_from_chunks(playbook_version_id: str, chunks: list[DocumentChunk]) -> list[Requirement]:
    requirements: list[Requirement] = []
    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            if not REQUIREMENT_RE.search(sentence):
                continue
            requirement = Requirement(
                id=f"req_{uuid4().hex[:12]}",
                playbook_version_id=playbook_version_id,
                chunk_id=chunk.id,
                title=(chunk.section_name or sentence[:80]).strip(),
                category=_infer_category(sentence),
                severity=_infer_severity(sentence).value,
                requirement_text=sentence,
                expected_documents_json=_infer_expected_documents(sentence),
                keywords_json=extract_keywords(sentence),
                page_number=chunk.page_number,
                section_name=chunk.section_name,
                metadata_json={"source_chunk_id": chunk.id},
            )
            requirements.append(requirement)
    if requirements:
        return requirements

    for chunk in chunks:
        requirements.append(
            Requirement(
                id=f"req_{uuid4().hex[:12]}",
                playbook_version_id=playbook_version_id,
                chunk_id=chunk.id,
                title=(chunk.section_name or chunk.text[:80]).strip(),
                category=_infer_category(chunk.text),
                severity=Severity.MEDIUM.value,
                requirement_text=chunk.text[:500],
                expected_documents_json=_infer_expected_documents(chunk.text),
                keywords_json=extract_keywords(chunk.text),
                page_number=chunk.page_number,
                section_name=chunk.section_name,
                metadata_json={"source_chunk_id": chunk.id, "fallback": True},
            )
        )
    return requirements


async def ingest_playbook(db: Session, *, name: str, effective_date: str, description: str | None, upload: UploadFile) -> dict:
    version_id = f"pb_{uuid4().hex[:12]}"
    job_id = f"job_{uuid4().hex[:12]}"
    stored_path = await persist_upload(upload, select_storage_dir(version_id))
    pages = extract_text_pages(stored_path)
    combined_text = "\n\n".join(page["text"] for page in pages)

    playbook = PlaybookVersion(
        id=version_id,
        name=name,
        effective_date=effective_date,
        description=description,
        source_filename=upload.filename or stored_path.name,
        source_path=str(stored_path),
        status=JobStage.COMPLETE.value,
        requirement_count=0,
    )
    job = Job(
        id=job_id,
        job_type="playbook_ingestion",
        target_id=version_id,
        status=JobStage.COMPLETE.value,
        progress=100,
        current_step="Playbook parsed, chunked, and indexed.",
        warnings_json=["OCR for scanned PDFs is not enabled; image-only documents may produce low recall."] if not combined_text else [],
    )
    document = Document(
        id=f"doc_{uuid4().hex[:12]}",
        owner_type="playbook",
        owner_id=version_id,
        document_type=DocumentType.OTHER.value,
        filename=upload.filename or stored_path.name,
        source_path=str(stored_path),
        content_type=upload.content_type,
        text_content=combined_text,
        page_count=len(pages),
        metadata_json={"kind": "playbook"},
    )
    db.add(playbook)
    db.add(job)
    db.add(document)
    db.flush()

    chunk_records: list[DocumentChunk] = []
    for chunk in chunk_pages(pages):
        chunk_records.append(
            DocumentChunk(
                id=f"chk_{uuid4().hex[:12]}",
                document_id=document.id,
                owner_type="playbook",
                owner_id=version_id,
                document_type=DocumentType.OTHER.value,
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

    requirements = _extract_requirements_from_chunks(version_id, chunk_records)
    db.add_all(requirements)
    playbook.requirement_count = len(requirements)
    db.commit()

    vector_store.upsert_chunks(
        owner_type="playbook",
        items=[
            {
                "id": chunk.id,
                "text": chunk.text,
                "metadata": {
                    "chunk_id": chunk.id,
                    "owner_id": version_id,
                    "page_number": chunk.page_number,
                    "document_type": chunk.document_type,
                },
            }
            for chunk in chunk_records
        ],
    )
    return {"job": job, "playbook": playbook}


def list_playbooks(db: Session) -> list[PlaybookVersion]:
    return db.scalars(select(PlaybookVersion).order_by(desc(PlaybookVersion.created_at))).all()


def get_playbook(db: Session, version_id: str) -> PlaybookVersion | None:
    if version_id == "active":
        return db.scalars(select(PlaybookVersion).order_by(desc(PlaybookVersion.created_at))).first()
    return db.get(PlaybookVersion, version_id)


def select_storage_dir(version_id: str):
    from app.core.settings import get_settings

    settings = get_settings()
    return settings.storage_root / "playbooks" / version_id
