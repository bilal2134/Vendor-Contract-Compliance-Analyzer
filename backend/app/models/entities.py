from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PlaybookVersion(Base):
    __tablename__ = "playbook_versions"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    effective_date: Mapped[str]
    description: Mapped[str | None]
    source_filename: Mapped[str]
    source_path: Mapped[str]
    status: Mapped[str]
    requirement_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(nullable=True)  # SHA-256 of uploaded file bytes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VendorPackage(Base):
    __tablename__ = "vendor_packages"

    id: Mapped[str] = mapped_column(primary_key=True)
    vendor_name: Mapped[str]
    playbook_version_id: Mapped[str] = mapped_column(ForeignKey("playbook_versions.id"))
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)
    owner_type: Mapped[str]
    owner_id: Mapped[str]
    document_type: Mapped[str]
    filename: Mapped[str]
    source_path: Mapped[str]
    content_type: Mapped[str | None]
    text_content: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    owner_type: Mapped[str]
    owner_id: Mapped[str]
    document_type: Mapped[str]
    chunk_index: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    section_name: Mapped[str | None]
    text: Mapped[str] = mapped_column(Text)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Requirement(Base):
    __tablename__ = "requirements"

    id: Mapped[str] = mapped_column(primary_key=True)
    playbook_version_id: Mapped[str] = mapped_column(ForeignKey("playbook_versions.id"))
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id"), nullable=True)
    title: Mapped[str]
    category: Mapped[str]
    severity: Mapped[str]
    requirement_text: Mapped[str] = mapped_column(Text)
    expected_documents_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_number: Mapped[int] = mapped_column(Integer, default=1)
    section_name: Mapped[str | None]
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(primary_key=True)
    job_type: Mapped[str]
    target_id: Mapped[str]
    status: Mapped[str]
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_step: Mapped[str]
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(primary_key=True)
    package_id: Mapped[str] = mapped_column(ForeignKey("vendor_packages.id"))
    playbook_version_id: Mapped[str] = mapped_column(ForeignKey("playbook_versions.id"))
    vendor_name: Mapped[str]
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    findings_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    conflicts_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewerNote(Base):
    __tablename__ = "reviewer_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str]
    note: Mapped[str] = mapped_column(Text)
    override_status: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
