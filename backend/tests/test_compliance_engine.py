from app.schemas.common import FindingStatus
from app.services.compliance_engine import MIN_RELEVANT_RETRIEVAL, _infer_status, _score_relevance


def test_low_relevance_evidence_is_treated_as_missing() -> None:
    requirement = "Exceptions shall be documented in the Vendor Risk Register with a specific remediation timeline not to exceed 180 days"
    irrelevant_chunk = "MASTER SERVICE AGREEMENT limitation of liability warranties and termination provisions"

    relevance = _score_relevance(requirement, ["vendor risk register", "remediation timeline"], irrelevant_chunk, 0.05)

    assert relevance == 0.0
    assert _infer_status(0.15, 0.05, False, True, False) == FindingStatus.MISSING


def test_non_compliant_requires_relevant_evidence() -> None:
    assert _infer_status(0.2, MIN_RELEVANT_RETRIEVAL + 0.05, False, True, True) == FindingStatus.NON_COMPLIANT