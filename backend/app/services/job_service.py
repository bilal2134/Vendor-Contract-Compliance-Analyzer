from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.schemas.common import DocumentType, FindingStatus, JobStage, Severity
from app.schemas.ingestion import CreatePackageRequest, CreatePlaybookVersionRequest
from app.services.repository import repository


def create_playbook_job(payload: CreatePlaybookVersionRequest) -> dict:
    version_id = f"pb_{uuid4().hex[:12]}"
    job_id = f"job_{uuid4().hex[:12]}"
    playbook = {
        "version_id": version_id,
        "name": payload.name,
        "effective_date": payload.effective_date,
        "description": payload.description,
        "status": JobStage.COMPLETE.value,
        "created_at": datetime.utcnow().isoformat(),
    }
    job = {
        "job_id": job_id,
        "playbook_version_id": version_id,
        "status": JobStage.COMPLETE.value,
        "progress": 100,
        "current_step": "Playbook structure captured and queued for chunking.",
        "warnings": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    repository.put("playbooks", version_id, playbook)
    repository.put("jobs", job_id, job)
    return {"job": job, "playbook": playbook}


def create_package_job(payload: CreatePackageRequest) -> dict:
    package_id = f"pkg_{uuid4().hex[:12]}"
    job_id = f"job_{uuid4().hex[:12]}"
    report_id = f"rpt_{uuid4().hex[:12]}"
    documents = [doc.model_dump() for doc in payload.documents]
    package = {
        "package_id": package_id,
        "vendor_name": payload.vendor_name,
        "playbook_version_id": payload.playbook_version_id,
        "documents": documents,
        "created_at": datetime.utcnow().isoformat(),
    }
    job = {
        "job_id": job_id,
        "package_id": package_id,
        "status": JobStage.COMPLETE.value,
        "progress": 100,
        "current_step": "Initial ingestion scaffold complete.",
        "warnings": [
            "Document parsing and embeddings are not wired yet; results are seeded demo data.",
        ],
        "created_at": datetime.utcnow().isoformat(),
    }
    report = {
        "report_id": report_id,
        "package_id": package_id,
        "vendor_name": payload.vendor_name,
        "playbook_version_id": payload.playbook_version_id,
        "summary": {
            "compliant": 1,
            "partial": 1,
            "non_compliant": 0,
            "missing": 1,
            "conflicts": 1,
        },
        "findings": [
            {
                "finding_id": f"fdg_{uuid4().hex[:12]}",
                "title": "Cyber liability coverage is present but not cross-referenced in the DPA",
                "category": "Insurance & Security",
                "severity": Severity.HIGH.value,
                "status": FindingStatus.PARTIAL.value,
                "summary": "The package includes evidence of 5M cyber liability coverage in the insurance certificate, but no explicit reference was found in the DPA.",
                "policy_citation": {
                    "source_id": "policy_4_2_1",
                    "source_name": "Procurement Playbook vCurrent",
                    "page": 347,
                    "section": "4.2.1 Cyber Liability Coverage",
                    "excerpt": "Vendors must maintain at least $5M cyber liability coverage and reference the coverage obligation in the DPA for data-processing engagements.",
                    "locator": "p347 s4.2.1",
                },
                "vendor_citations": [
                    {
                        "source_id": "doc_insurance_01",
                        "source_name": "Insurance Certificate",
                        "page": 2,
                        "section": "Cyber Liability",
                        "excerpt": "$5,000,000 aggregate cyber liability coverage is listed as active through 2026.",
                        "locator": "p2 cyber liability",
                    }
                ],
                "confidence": 0.82,
                "confidence_breakdown": {
                    "extraction": 0.83,
                    "retrieval": 0.78,
                    "grounding": 0.94,
                    "rule_completion": 0.72,
                },
                "search_summary": "Searched DPA chunks and structured clause references for insurance obligations; no direct cross-reference was found.",
            },
            {
                "finding_id": f"fdg_{uuid4().hex[:12]}",
                "title": "Termination notice language is inconsistent across submitted documents",
                "category": "Commercial Terms",
                "severity": Severity.CRITICAL.value,
                "status": FindingStatus.CONFLICT.value,
                "summary": "The MSA states a 30-day termination notice while the company profile references a 60-day notice period.",
                "policy_citation": {
                    "source_id": "policy_2_7",
                    "source_name": "Procurement Playbook vCurrent",
                    "page": 118,
                    "section": "2.7 Termination Standards",
                    "excerpt": "Termination periods must be consistent across governing commercial documents and ancillary materials.",
                    "locator": "p118 s2.7",
                },
                "vendor_citations": [
                    {
                        "source_id": "doc_msa_01",
                        "source_name": "Master Service Agreement",
                        "page": 14,
                        "section": "Termination",
                        "excerpt": "Either party may terminate this Agreement on thirty (30) days' written notice.",
                        "locator": "p14 termination",
                    },
                    {
                        "source_id": "doc_profile_01",
                        "source_name": "Company Profile",
                        "page": 6,
                        "section": "Engagement Model",
                        "excerpt": "Standard customer notice period is sixty (60) days before termination.",
                        "locator": "p6 engagement model",
                    }
                ],
                "confidence": 0.89,
                "confidence_breakdown": {
                    "extraction": 0.91,
                    "retrieval": 0.86,
                    "grounding": 0.96,
                    "rule_completion": 0.84,
                },
                "search_summary": "Structured comparison found contradictory duration values for termination notice.",
            },
            {
                "finding_id": f"fdg_{uuid4().hex[:12]}",
                "title": "Data retention schedule is not evidenced in the package",
                "category": "Data Governance",
                "severity": Severity.HIGH.value,
                "status": FindingStatus.MISSING.value,
                "summary": "No retention schedule or deletion timeline was found in the submitted MSA, DPA, security materials, or profile.",
                "policy_citation": {
                    "source_id": "policy_5_4_3",
                    "source_name": "Procurement Playbook vCurrent",
                    "page": 402,
                    "section": "5.4.3 Data Retention Requirements",
                    "excerpt": "All data-processing vendors must commit to documented retention periods and deletion timelines aligned to company schedules.",
                    "locator": "p402 s5.4.3",
                },
                "vendor_citations": [],
                "confidence": 0.67,
                "confidence_breakdown": {
                    "extraction": 0.74,
                    "retrieval": 0.63,
                    "grounding": 0.88,
                    "rule_completion": 0.44,
                },
                "search_summary": "Searched all uploaded document types for retention, deletion, archive, and schedule terminology. No qualifying clause was found, but OCR and retrieval are not yet implemented.",
            }
        ],
        "conflicts": [
            {
                "conflict_id": f"cnf_{uuid4().hex[:12]}",
                "title": "Termination notice mismatch",
                "summary": "Vendor package includes conflicting termination notice periods between the MSA and company profile.",
                "left_citation": {
                    "source_id": "doc_msa_01",
                    "source_name": "Master Service Agreement",
                    "page": 14,
                    "section": "Termination",
                    "excerpt": "Either party may terminate this Agreement on thirty (30) days' written notice.",
                    "locator": "p14 termination",
                },
                "right_citation": {
                    "source_id": "doc_profile_01",
                    "source_name": "Company Profile",
                    "page": 6,
                    "section": "Engagement Model",
                    "excerpt": "Standard customer notice period is sixty (60) days before termination.",
                    "locator": "p6 engagement model",
                },
                "severity": Severity.CRITICAL.value,
            }
        ],
        "created_at": datetime.utcnow().isoformat(),
    }

    repository.put("packages", package_id, package)
    repository.put("jobs", job_id, job)
    repository.put("reports", report_id, report)
    return {"job": job, "package": package, "report": report}


def get_job(job_id: str) -> dict | None:
    return repository.get("jobs", job_id)


def get_report(report_id: str) -> dict | None:
    return repository.get("reports", report_id)


def list_dashboard_cards() -> list[dict]:
    cards = []
    for report in repository.values("reports"):
        cards.append(
            {
                "package_id": report["package_id"],
                "vendor_name": report["vendor_name"],
                "status": "ready",
                "critical_findings": report["summary"]["conflicts"] + report["summary"]["missing"],
                "report_id": report["report_id"],
            }
        )
    return cards


def add_reviewer_note(finding_id: str, note: str, override_status: str | None) -> dict:
    entry = {
        "finding_id": finding_id,
        "note": note,
        "override_status": override_status,
        "created_at": datetime.utcnow().isoformat(),
    }
    repository.notes.setdefault(finding_id, []).append(entry)
    return entry


def get_reviewer_notes(finding_id: str) -> list[dict]:
    return repository.notes.get(finding_id, [])
