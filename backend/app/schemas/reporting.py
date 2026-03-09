from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Citation, ConfidenceBreakdown, FindingStatus, Severity, TimestampedModel


class Finding(BaseModel):
    finding_id: str
    title: str
    category: str
    severity: Severity
    status: FindingStatus
    summary: str
    policy_citation: Citation
    vendor_citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown
    search_summary: str


class ConflictRecord(BaseModel):
    conflict_id: str
    title: str
    summary: str
    left_citation: Citation
    right_citation: Citation
    severity: Severity


class ReportSummary(BaseModel):
    compliant: int
    partial: int
    non_compliant: int
    missing: int
    conflicts: int


class PackageReport(TimestampedModel):
    report_id: str
    package_id: str
    vendor_name: str
    playbook_version_id: str
    summary: ReportSummary
    findings: list[Finding]
    conflicts: list[ConflictRecord]


class DashboardCard(BaseModel):
    package_id: str
    vendor_name: str
    status: str
    critical_findings: int
    report_id: str | None = None


class DashboardResponse(BaseModel):
    cards: list[DashboardCard]


class ReviewerNoteRequest(BaseModel):
    note: str = Field(min_length=3, max_length=4000)
    override_status: FindingStatus | None = None
