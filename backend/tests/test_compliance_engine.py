from datetime import datetime

from app.schemas.common import FindingStatus
from app.services.compliance_engine import (
    MIN_RELEVANT_RETRIEVAL,
    _evaluate_disqualification_signals,
    _extract_soc2_dates,
    _has_anti_assignment_clause,
    _infer_status,
    _score_relevance,
)


def test_low_relevance_evidence_is_treated_as_missing() -> None:
    requirement = "Exceptions shall be documented in the Vendor Risk Register with a specific remediation timeline not to exceed 180 days"
    irrelevant_chunk = "MASTER SERVICE AGREEMENT limitation of liability warranties and termination provisions"

    relevance = _score_relevance(requirement, ["vendor risk register", "remediation timeline"], irrelevant_chunk, 0.05)

    assert relevance == 0.0
    assert _infer_status(0.15, 0.05, False, True, False) == FindingStatus.MISSING


def test_non_compliant_requires_relevant_evidence() -> None:
    assert _infer_status(0.2, MIN_RELEVANT_RETRIEVAL + 0.05, False, True, True) == FindingStatus.NON_COMPLIANT


def test_disqualification_self_attestations_count_as_evidence() -> None:
    texts = [
        "OFAC/Sanctions: No designations. Last screened January 5, 2026.",
        "Export Controls: EAR/ITAR compliant. No ITAR-controlled products.",
        "Debarment (GSA): Not listed on SAM.gov excluded parties.",
        "H.5 Sanctions: No OFAC, EU, or UN sanctions designations.",
    ]

    signals = _evaluate_disqualification_signals(texts)

    assert signals == {
        "ofac": True,
        "eu": True,
        "export": True,
        "sam": True,
    }


def test_assignment_detector_ignores_insolvency_assignment_reference() -> None:
    insolvency_clause = "Either party may terminate immediately if the other party makes a general assignment for the benefit of creditors."
    anti_assignment_clause = (
        "Vendors may not assign, transfer, or delegate any rights or obligations under the MSA without prior written consent of the Company. "
        "Any purported assignment in violation of this clause is null and void."
    )

    assert not _has_anti_assignment_clause(insolvency_clause)
    assert _has_anti_assignment_clause(anti_assignment_clause)


def test_extract_soc2_dates_parses_report_and_audit_end() -> None:
    text = (
        "Audit Period: October 1, 2024 - September 30, 2025\n"
        "Report Date: November 15, 2025"
    )

    report_date, audit_end = _extract_soc2_dates(text)

    assert report_date == datetime(2025, 11, 15)
    assert audit_end == datetime(2025, 9, 30)