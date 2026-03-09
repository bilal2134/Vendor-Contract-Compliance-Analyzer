from __future__ import annotations

import re
from collections import Counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk, Requirement, VendorPackage
from app.schemas.common import ConfidenceBreakdown, FindingStatus, Severity
from app.services.gemini_service import gemini_service
from app.services.vector_store import vector_store

MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([mMkK]|million|billion)?")
NOTICE_RE = re.compile(
    r"(\d{1,4})\s*[- ]?(day|days|month|months|year|years)(?:\s+(?:written\s+)?notice|\s+before\s+termination|\s+prior\s+to\s+termination)",
    re.IGNORECASE,
)
RETENTION_RE = re.compile(r"(\d{1,4})\s*[- ]?(day|days|month|months|year|years)\s+(?:retention|retain|retained|deletion|delete)", re.IGNORECASE)
CERT_RE = re.compile(r"(soc\s*2|iso\s*27001|hipaa|pci[- ]dss)", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")


def _parse_money_values(text: str) -> list[float]:
    amounts: list[float] = []
    for raw_amount, scale in MONEY_RE.findall(text):
        value = float(raw_amount.replace(",", ""))
        normalized_scale = scale.lower() if scale else ""
        if normalized_scale in {"m", "million"}:
            value *= 1_000_000
        elif normalized_scale in {"b", "billion"}:
            value *= 1_000_000_000
        elif normalized_scale == "k":
            value *= 1_000
        amounts.append(value)
    return amounts


def _parse_duration_days(text: str, pattern: re.Pattern[str]) -> list[int]:
    unit_days = {"day": 1, "days": 1, "month": 30, "months": 30, "year": 365, "years": 365}
    values: list[int] = []
    for amount, unit in pattern.findall(text):
        values.append(int(amount) * unit_days[unit.lower()])
    return values


def _extract_certs(text: str) -> list[str]:
    return sorted({match.upper().replace("  ", " ") for match in CERT_RE.findall(text)})


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


def _score_lexical(query: str, text: str) -> float:
    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


def _infer_status(rule_completion: float, retrieval_score: float, has_conflict: bool, has_evidence: bool) -> FindingStatus:
    if has_conflict:
        return FindingStatus.CONFLICT
    if rule_completion >= 0.88:
        return FindingStatus.COMPLIANT
    if has_evidence and rule_completion >= 0.45:
        return FindingStatus.PARTIAL
    if not has_evidence and retrieval_score < 0.15:
        return FindingStatus.MISSING
    if has_evidence:
        return FindingStatus.NON_COMPLIANT
    return FindingStatus.MISSING


def _serialize_citation(chunk: DocumentChunk, document_lookup: dict[str, Document]) -> dict:
    document = document_lookup[chunk.document_id]
    section = chunk.section_name or chunk.metadata_json.get("section_name")
    return {
        "source_id": chunk.id,
        "source_name": document.filename,
        "page": chunk.page_number,
        "section": section,
        "excerpt": chunk.text[:600],
        "locator": f"p{chunk.page_number} c{chunk.chunk_index}",
    }


def _infer_requirement_title(requirement: Requirement) -> str:
    if requirement.title:
        return requirement.title
    return requirement.requirement_text[:90]


def _detect_global_conflicts(chunks: list[DocumentChunk], document_lookup: dict[str, Document]) -> list[dict]:
    conflicts: list[dict] = []
    notice_evidence: list[tuple[int, DocumentChunk]] = []
    for chunk in chunks:
        for value in _parse_duration_days(chunk.text, NOTICE_RE):
            notice_evidence.append((value, chunk))
    unique_notice_values = sorted({value for value, _ in notice_evidence})
    if len(unique_notice_values) > 1:
        chosen_chunks: list[DocumentChunk] = []
        seen_values: set[int] = set()
        for value, chunk in notice_evidence:
            if value in seen_values:
                continue
            chosen_chunks.append(chunk)
            seen_values.add(value)
            if len(chosen_chunks) == 2:
                break
        if len(chosen_chunks) == 2:
            conflicts.append(
                {
                    "conflict_id": f"cnf_{uuid4().hex[:12]}",
                    "title": "Termination notice mismatch",
                    "summary": "Conflicting termination notice periods were found across uploaded vendor documents.",
                    "left_citation": _serialize_citation(chosen_chunks[0], document_lookup),
                    "right_citation": _serialize_citation(chosen_chunks[1], document_lookup),
                    "severity": Severity.CRITICAL.value,
                }
            )
    return conflicts


def build_report(db: Session, package: VendorPackage, playbook_version_id: str) -> dict:
    requirements = db.scalars(
        select(Requirement).where(Requirement.playbook_version_id == playbook_version_id).order_by(Requirement.page_number)
    ).all()
    documents = db.scalars(
        select(Document).where(Document.owner_type == "package", Document.owner_id == package.id)
    ).all()
    document_lookup = {document.id: document for document in documents}
    chunks = db.scalars(
        select(DocumentChunk).where(DocumentChunk.owner_type == "package", DocumentChunk.owner_id == package.id)
    ).all()
    chunk_lookup = {chunk.id: chunk for chunk in chunks}

    findings: list[dict] = []
    conflicts: list[dict] = []
    summary_counter: Counter[str] = Counter()

    for requirement in requirements:
        requirement_query = requirement.requirement_text
        candidate_results = vector_store.query(
            owner_type="vendor",
            query_text=requirement_query,
            where={"owner_id": package.id},
            top_k=6,
        )
        matched_chunks: list[DocumentChunk] = []
        retrieval_scores: list[float] = []
        for result in candidate_results:
            chunk_id = result["metadata"].get("chunk_id")
            if chunk_id in chunk_lookup:
                matched_chunks.append(chunk_lookup[chunk_id])
                retrieval_scores.append(result["score"])

        if not matched_chunks:
            lexical_ranked = sorted(
                chunks,
                key=lambda item: _score_lexical(requirement_query, item.text),
                reverse=True,
            )[:6]
            matched_chunks = [chunk for chunk in lexical_ranked if _score_lexical(requirement_query, chunk.text) > 0.05]
            retrieval_scores = [_score_lexical(requirement_query, chunk.text) for chunk in matched_chunks]

        combined_text = " \n".join(chunk.text for chunk in matched_chunks)
        lower_requirement = requirement.requirement_text.lower()
        money_requirements = _parse_money_values(requirement.requirement_text)
        money_evidence = _parse_money_values(combined_text)
        notice_values = []
        retention_values = []
        cert_values: list[str] = []
        for chunk in matched_chunks:
            notice_values.extend(_parse_duration_days(chunk.text, NOTICE_RE))
            retention_values.extend(_parse_duration_days(chunk.text, RETENTION_RE))
            cert_values.extend(_extract_certs(chunk.text))

        expected_documents = set(requirement.expected_documents_json or [])
        referenced_document_types = {chunk.document_type for chunk in matched_chunks}
        document_scope_coverage = 1.0 if not expected_documents else len(referenced_document_types & expected_documents) / len(expected_documents)
        retrieval_score = max(retrieval_scores) if retrieval_scores else 0.0
        extraction_score = min(1.0, 0.55 + (0.07 * len(matched_chunks))) if matched_chunks else 0.25
        grounding_score = 0.95 if matched_chunks else 0.5
        has_conflict = False
        rule_completion = 0.0
        vendor_citations = [_serialize_citation(chunk, document_lookup) for chunk in matched_chunks[:3]]
        search_summary = "Searched the uploaded package using hybrid lexical and vector retrieval."
        fallback_summary = "Relevant evidence was reviewed for this requirement."

        if "cyber" in lower_requirement and ("coverage" in lower_requirement or "insurance" in lower_requirement):
            required_amount = max(money_requirements) if money_requirements else 0.0
            found_amount = max(money_evidence) if money_evidence else 0.0
            amount_score = 1.0 if required_amount == 0.0 or found_amount >= required_amount else (found_amount / required_amount if required_amount else 0.0)
            cross_reference_needed = "dpa" in lower_requirement or "data processing" in lower_requirement
            dpa_reference = any(chunk.document_type == "dpa" and ("insurance" in chunk.text.lower() or "cyber" in chunk.text.lower()) for chunk in matched_chunks)
            rule_completion = (amount_score * 0.7) + ((1.0 if dpa_reference or not cross_reference_needed else 0.0) * 0.3)
            if cross_reference_needed and not dpa_reference and found_amount >= required_amount:
                search_summary = "Coverage evidence was found, but the required DPA cross-reference was not located in the uploaded DPA text."
            elif found_amount < required_amount and money_evidence:
                search_summary = "Insurance evidence was found, but the stated coverage appears below the required threshold."
            elif not money_evidence:
                search_summary = "No qualifying insurance amount was found in the uploaded package."
            fallback_summary = (
                f"Required cyber coverage threshold is {required_amount:,.0f} and the best supporting evidence in the package is {found_amount:,.0f}."
                if required_amount or found_amount
                else "The requirement expects cyber insurance coverage evidence in the package."
            )
        elif "termination" in lower_requirement and "consistent" in lower_requirement:
            all_notice_values: list[tuple[int, DocumentChunk]] = []
            for chunk in chunks:
                for value in _parse_duration_days(chunk.text, NOTICE_RE):
                    all_notice_values.append((value, chunk))
            unique_values = sorted({value for value, _ in all_notice_values})
            has_conflict = len(unique_values) > 1
            rule_completion = 1.0 if len(unique_values) == 1 and unique_values else 0.0
            if has_conflict:
                conflicting_chunks: list[DocumentChunk] = []
                seen_values: set[int] = set()
                for value, chunk in all_notice_values:
                    if value not in seen_values:
                        conflicting_chunks.append(chunk)
                        seen_values.add(value)
                    if len(conflicting_chunks) == 2:
                        break
                if len(conflicting_chunks) == 2:
                    conflicts.append(
                        {
                            "conflict_id": f"cnf_{uuid4().hex[:12]}",
                            "title": _infer_requirement_title(requirement),
                            "summary": "Conflicting termination notice periods were found across vendor documents.",
                            "left_citation": _serialize_citation(conflicting_chunks[0], document_lookup),
                            "right_citation": _serialize_citation(conflicting_chunks[1], document_lookup),
                            "severity": Severity.CRITICAL.value,
                        }
                    )
                    vendor_citations = [_serialize_citation(chunk, document_lookup) for chunk in conflicting_chunks]
                search_summary = "Structured duration extraction found inconsistent termination notice periods across the package."
            else:
                search_summary = "Termination notice language appears consistent across the package evidence that was found."
            fallback_summary = "Termination notice terms were compared across vendor documents to detect contradictions."
        elif "retention" in lower_requirement or "deletion" in lower_requirement:
            rule_completion = 1.0 if retention_values else 0.0
            if retention_values:
                search_summary = "Retention or deletion language was found in the uploaded package."
            else:
                search_summary = "No retention schedule or deletion timeline was found across the uploaded package documents."
            fallback_summary = "The requirement expects a documented retention or deletion timeline in the package."
        elif "certification" in lower_requirement or "soc 2" in lower_requirement or "iso 27001" in lower_requirement:
            certifications = sorted(set(cert_values))
            mentioned_in_msa = any(chunk.document_type == "msa" and any(cert.lower() in chunk.text.lower() for cert in certifications) for chunk in matched_chunks)
            rule_completion = 1.0 if certifications and (mentioned_in_msa or "msa" not in lower_requirement) else 0.45 if certifications else 0.0
            if certifications and not mentioned_in_msa and "msa" in lower_requirement:
                search_summary = "Security certifications were found, but the MSA does not appear to reference them."
            elif certifications:
                search_summary = f"Detected certifications in the package: {', '.join(certifications)}."
            else:
                search_summary = "No qualifying certification evidence was found in the uploaded package."
            fallback_summary = "The package was checked for certifications and related contractual references."
        else:
            keyword_hits = sum(1 for keyword in requirement.keywords_json if keyword in combined_text.lower())
            keyword_total = max(1, len(requirement.keywords_json))
            rule_completion = min(1.0, max(retrieval_score, keyword_hits / keyword_total) * max(0.5, document_scope_coverage))
            search_summary = "Compared requirement keywords and related chunk evidence across the uploaded documents."
            fallback_summary = "The system gathered the most relevant package excerpts for this requirement and measured evidence coverage."

        status = _infer_status(rule_completion, retrieval_score, has_conflict, bool(matched_chunks))
        if status == FindingStatus.CONFLICT:
            severity = Severity.CRITICAL
        else:
            severity = Severity(requirement.severity)
        confidence_breakdown = ConfidenceBreakdown(
            extraction=min(1.0, extraction_score),
            retrieval=min(1.0, retrieval_score if retrieval_score > 0 else 0.2),
            grounding=grounding_score,
            rule_completion=min(1.0, max(0.0, rule_completion)),
        )
        confidence = (
            confidence_breakdown.extraction * 0.2
            + confidence_breakdown.retrieval * 0.25
            + confidence_breakdown.grounding * 0.25
            + confidence_breakdown.rule_completion * 0.3
        )
        title = _infer_requirement_title(requirement)
        policy_citation = {
            "source_id": requirement.id,
            "source_name": f"Playbook {playbook_version_id}",
            "page": requirement.page_number,
            "section": requirement.section_name,
            "excerpt": requirement.requirement_text,
            "locator": f"p{requirement.page_number}",
        }
        evidence_text = [citation["excerpt"] for citation in vendor_citations]
        summary = gemini_service.summarize_finding(requirement.requirement_text, evidence_text, fallback_summary)

        findings.append(
            {
                "finding_id": f"fdg_{uuid4().hex[:12]}",
                "title": title,
                "category": requirement.category,
                "severity": severity.value,
                "status": status.value,
                "summary": summary,
                "policy_citation": policy_citation,
                "vendor_citations": vendor_citations,
                "confidence": round(confidence, 2),
                "confidence_breakdown": confidence_breakdown.model_dump(),
                "search_summary": search_summary,
            }
        )
        summary_counter[status.value] += 1

    global_conflicts = _detect_global_conflicts(chunks, document_lookup)
    existing_pairs = {
        (conflict["left_citation"]["source_id"], conflict["right_citation"]["source_id"]) for conflict in conflicts
    }
    for conflict in global_conflicts:
        pair = (conflict["left_citation"]["source_id"], conflict["right_citation"]["source_id"])
        if pair not in existing_pairs:
            conflicts.append(conflict)

    return {
        "summary": {
            "compliant": summary_counter[FindingStatus.COMPLIANT.value],
            "partial": summary_counter[FindingStatus.PARTIAL.value],
            "non_compliant": summary_counter[FindingStatus.NON_COMPLIANT.value],
            "missing": summary_counter[FindingStatus.MISSING.value],
            "conflicts": len(conflicts) or summary_counter[FindingStatus.CONFLICT.value],
        },
        "findings": findings,
        "conflicts": conflicts,
    }
