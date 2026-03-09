from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    MSA = "msa"
    DPA = "dpa"
    SECURITY = "security"
    INSURANCE = "insurance"
    PROFILE = "profile"
    OTHER = "other"


class JobStage(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    INDEXING = "indexing"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


class FindingStatus(str, Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    MISSING = "missing"
    CONFLICT = "conflict"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceBreakdown(BaseModel):
    extraction: float = Field(ge=0.0, le=1.0)
    retrieval: float = Field(ge=0.0, le=1.0)
    grounding: float = Field(ge=0.0, le=1.0)
    rule_completion: float = Field(ge=0.0, le=1.0)


class Citation(BaseModel):
    source_id: str
    source_name: str
    page: int | None = None
    section: str | None = None
    excerpt: str
    locator: str | None = None


class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
