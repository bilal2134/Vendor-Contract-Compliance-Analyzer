from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk, Job, PlaybookVersion, Requirement
from app.schemas.common import DocumentType, JobStage, Severity
from app.services.chunking import chunk_pages, extract_keywords, split_sentences
from app.services.requirement_utils import expand_keywords, is_actionable_requirement, requirement_priority, select_actionable_requirements
from app.services.storage import persist_upload
from app.services.text_extraction import extract_text_pages
from app.services.vector_store import vector_store


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
    if any(token in lower for token in ["vendor risk register", "exception", "remediation"]):
        documents.extend([DocumentType.MSA.value, DocumentType.DPA.value, DocumentType.PROFILE.value])
    if any(token in lower for token in ["hierarchy of documents", "order of precedence", "entire agreement", "incorporated"]):
        documents.extend([DocumentType.MSA.value, DocumentType.DPA.value, DocumentType.PROFILE.value])
    deduped: list[str] = []
    seen: set[str] = set()
    for document_type in documents:
        if document_type not in seen:
            deduped.append(document_type)
            seen.add(document_type)
    return deduped or [DocumentType.MSA.value, DocumentType.DPA.value, DocumentType.SECURITY.value, DocumentType.INSURANCE.value]


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
    seen_sentences: set[str] = set()
    for chunk in chunks:
        for sentence in split_sentences(chunk.text):
            normalized_sentence = " ".join(sentence.split())
            if normalized_sentence in seen_sentences:
                continue
            if not is_actionable_requirement(normalized_sentence, chunk.section_name):
                continue
            seen_sentences.add(normalized_sentence)
            requirement = Requirement(
                id=f"req_{uuid4().hex[:12]}",
                playbook_version_id=playbook_version_id,
                chunk_id=chunk.id,
                title=(chunk.section_name or normalized_sentence[:80]).strip(),
                category=_infer_category(normalized_sentence),
                severity=_infer_severity(normalized_sentence).value,
                requirement_text=normalized_sentence,
                expected_documents_json=_infer_expected_documents(normalized_sentence),
                keywords_json=expand_keywords(normalized_sentence, extract_keywords(normalized_sentence), chunk.section_name),
                page_number=chunk.page_number,
                section_name=chunk.section_name,
                metadata_json={
                    "source_chunk_id": chunk.id,
                    "priority": requirement_priority(normalized_sentence, chunk.section_name),
                },
            )
            requirements.append(requirement)
    return select_actionable_requirements(requirements)


async def ingest_playbook(db: Session, *, name: str, effective_date: str, description: str | None, upload: UploadFile) -> dict:
    # Read bytes upfront to compute hash and detect duplicates before any DB/disk writes
    file_bytes = await upload.read()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    await upload.seek(0)

    existing = db.scalars(
        select(PlaybookVersion).where(PlaybookVersion.content_hash == content_hash)
    ).first()
    if existing is not None:
        raise ValueError(
            f"duplicate: this file has already been uploaded as '{existing.name}' "
            f"(version {existing.id}, created {existing.created_at.date()}). "
            "Upload a different file or use the existing playbook."
        )

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
        content_hash=content_hash,
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
