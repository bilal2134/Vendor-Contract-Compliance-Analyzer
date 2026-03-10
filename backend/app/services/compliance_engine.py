from __future__ import annotations

import logging
import re
from calendar import monthrange
from collections import Counter
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk, Requirement, VendorPackage
from app.schemas.common import ConfidenceBreakdown, FindingStatus, Severity
from app.services.gemini_service import gemini_service
from app.services.requirement_utils import build_requirement_aliases, select_actionable_requirements
from app.services.vector_store import vector_store

log = logging.getLogger(__name__)

MONEY_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*([mMkK]|million|billion)?")
NOTICE_RE = re.compile(
    r"(\d{1,4})\s*[- ]?(day|days|month|months|year|years)(?:\s+(?:written\s+)?notice|\s+before\s+termination|\s+prior\s+to\s+termination)",
    re.IGNORECASE,
)
RETENTION_RE = re.compile(r"(\d{1,4})\s*[- ]?(day|days|month|months|year|years)\s+(?:retention|retain|retained|deletion|delete)", re.IGNORECASE)
REMEDIATION_RE = re.compile(r"(\d{1,4})\s*[- ]?(day|days|month|months|year|years)\s+(?:remediation|remediate|remediation\s+timeline)", re.IGNORECASE)
CERT_RE = re.compile(r"(soc\s*2|iso\s*27001|hipaa|pci[- ]dss)", re.IGNORECASE)
WITHIN_TIME_RE = re.compile(
    r"within\s+(\d{1,4})\s*(?:calendar\s+|business\s+)?[- ]?(hour|hours|minute|minutes|day|days)",
    re.IGNORECASE,
)
BROAD_RETENTION_RE = re.compile(
    r"(\d{1,4})\s*(?:calendar\s+|business\s+)?[- ]?(day|days|month|months|year|years)",
    re.IGNORECASE,
)
CERT_VALID_THROUGH_RE = re.compile(
    r"valid\s+through\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
CONTRACT_EFFECTIVE_DATE_RE = re.compile(
    r"effective\s+date\s*:?\s*(\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
CONTRACT_TERM_MONTHS_RE = re.compile(
    r"(?:initial\s+)?term\s+of\s+(\d+)\s+months",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9-]{2,}")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "into",
    "under",
    "this",
    "that",
    "these",
    "those",
    "shall",
    "must",
    "will",
    "may",
    "any",
    "all",
    "are",
    "was",
    "were",
    "been",
    "being",
    "than",
    "each",
    "such",
    "vendor",
    "vendors",
    "company",
    "corporate",
    "solutions",
    "agreement",
    "service",
    "services",
    "contract",
    "contracts",
    "policy",
    "requirement",
    "requirements",
    "section",
    "clause",
    "terms",
    "applicable",
    "written",
}
MIN_RELEVANT_RETRIEVAL = 0.18


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


def _parse_duration_hours(text: str, pattern: re.Pattern) -> list[float]:
    """Parse duration values matching *pattern* and return them as hours."""
    unit_hours: dict[str, float] = {
        "hour": 1.0, "hours": 1.0,
        "minute": 1.0 / 60, "minutes": 1.0 / 60,
        "day": 24.0, "days": 24.0,
    }
    values: list[float] = []
    for amount, unit in pattern.findall(text):
        mul = unit_hours.get(unit.lower())
        if mul is not None:
            values.append(int(amount) * mul)
    return values


def _parse_cert_date(date_str: str) -> datetime | None:
    """Parse a date string (e.g. 'April 30, 2026') into a datetime."""
    normalized = re.sub(r",?\s+", " ", date_str.strip()).title()
    for fmt in ("%B %d %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def _add_months(d: datetime, months: int) -> datetime:
    """Return *d* advanced by *months* calendar months."""
    year = d.year + (d.month + months - 1) // 12
    month = (d.month + months - 1) % 12 + 1
    day = min(d.day, monthrange(year, month)[1])
    return datetime(year, month, day)


def _section_relevance_boost(requirement_text: str, section_name: str | None) -> float:
    """Return a score boost [0, 0.25] when the chunk's section heading aligns with the requirement topic.

    After the .txt section-split fix, DPA Article 9 sub-sections carry names like
    '9.2 Retention Schedule Applicability', giving this boost reliable signal.
    """
    if not section_name:
        return 0.0
    lower_section = section_name.lower()
    lower_req = requirement_text.lower()
    boosts = [
        (
            ["retention", "deletion", "retain", "destroy", "drs", "nist sp 800"],
            ["retention", "deletion", "article 9", "data ret", "destruction", "9.1", "9.2", "9.3", "9.4"],
        ),
        (
            ["data subject", "erasure", "portability", "rectif", "72 hour", "subject rights"],
            ["data subject", "article 6", "subject rights", "rights request", "response timeline"],
        ),
        (
            ["encryption", "tls", "aes", "encrypt", "key rotation", "key management"],
            ["encryption", "section d", "cryptograph", "data protection"],
        ),
        (
            ["certification", "soc 2", "iso 27001", "fedramp"],
            ["certification", "section b", "iso 27001", "soc", "certif"],
        ),
        (
            ["insurance", "coverage", "cyber"],
            ["insurance", "section g", "section 7", "indemnif"],
        ),
    ]
    for req_triggers, section_words in boosts:
        if any(trigger in lower_req for trigger in req_triggers):
            if any(word in lower_section for word in section_words):
                return 0.25
    return 0.0


def _doc_type_affinity(requirement_text: str, doc_type: str | None) -> float:
    """Return a score multiplier [0.55, 1.1] based on how well *doc_type* aligns with the requirement topic.

    Penalises irrelevant doc types (e.g. MSA for a data-retention requirement) and rewards
    the most likely authoritative source (e.g. DPA for personal-data obligations).
    """
    if not doc_type:
        return 0.85
    lower_req = requirement_text.lower()
    lower_type = doc_type.lower()
    dpa_topics = [
        "retention", "deletion", "data subject", "erasure", "portability",
        "personal data", "processor", "data protection", "gdpr", "destroy",
        "nist sp 800", "certificate of destruction",
    ]
    sec_topics = [
        "encryption", "tls", "aes", "key rotation", "soc 2", "iso 27001",
        "vulnerability", "penetration", "mfa", "fedramp", "certification",
    ]
    ins_topics = ["insurance", "coverage", "indemnif", "cyber liability"]
    dpa_hits = sum(1 for kw in dpa_topics if kw in lower_req)
    sec_hits = sum(1 for kw in sec_topics if kw in lower_req)
    ins_hits = sum(1 for kw in ins_topics if kw in lower_req)
    if dpa_hits >= 1:
        if "dpa" in lower_type:
            return 1.1
        if "msa" in lower_type:
            return 0.55   # MSA rarely relevant for DPA-topic requirements
        if "security" in lower_type:
            return 0.70
    if sec_hits >= 1:
        if "security" in lower_type:
            return 1.1
        if "dpa" in lower_type:
            return 0.65   # DPA rarely contains per-protocol encryption specifics
    if ins_hits >= 1:
        if "insurance" in lower_type:
            return 1.1
        if "dpa" in lower_type:
            return 0.60
    return 0.85


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text) if token.lower() not in STOPWORDS}


def _score_lexical(query: str, text: str) -> float:
    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = len(query_tokens & text_tokens)
    return overlap / len(query_tokens)


def _score_keyword_coverage(keywords: list[str], text: str) -> float:
    normalized_keywords = [keyword.strip().lower() for keyword in keywords if keyword and keyword.strip()]
    if not normalized_keywords:
        return 0.0
    haystack = text.lower()
    hits = sum(1 for keyword in normalized_keywords if keyword in haystack)
    return hits / len(normalized_keywords)


def _score_relevance(query: str, keywords: list[str], text: str, vector_score: float = 0.0) -> float:
    lexical_score = _score_lexical(query, text)
    keyword_score = _score_keyword_coverage(keywords, text)
    anchored_vector = vector_score if vector_score >= 0.6 and (lexical_score >= 0.08 or keyword_score >= 0.08) else 0.0
    if keyword_score >= 0.2 or lexical_score >= 0.14 or anchored_vector > 0.0:
        return max(lexical_score, keyword_score, anchored_vector)
    return 0.0


def _infer_status(
    rule_completion: float,
    retrieval_score: float,
    has_conflict: bool,
    has_evidence: bool,
    has_relevant_evidence: bool,
) -> FindingStatus:
    if has_conflict:
        return FindingStatus.CONFLICT
    if not has_evidence or not has_relevant_evidence or retrieval_score < MIN_RELEVANT_RETRIEVAL:
        return FindingStatus.MISSING
    if rule_completion >= 0.88:
        return FindingStatus.COMPLIANT
    if rule_completion >= 0.45:
        return FindingStatus.PARTIAL
    return FindingStatus.NON_COMPLIANT


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


def _build_query_text(requirement: Requirement) -> str:
    aliases = build_requirement_aliases(requirement.requirement_text, requirement.section_name)
    return " ".join([requirement.requirement_text, *aliases[:4]])


def _build_query_where(package_id: str, expected_documents: set[str]) -> dict:
    if expected_documents and len(expected_documents) <= 4:
        return {
            "$and": [
                {"owner_id": package_id},
                {"document_type": {"$in": sorted(expected_documents)}},
            ]
        }
    return {"owner_id": package_id}


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


# ── Conflict field definitions ─────────────────────────────────────────────────
# Each entry declares a named field, the patterns used to extract it from each
# document, and the severity if different documents disagree.
#
# "extract" receives the full text of one chunk and returns a canonical string
# (or None when the field is not present).  The comparison uses the *set* of
# distinct values across all doc-types; size > 1 → conflict.

def _val_days(text: str, pattern: re.Pattern) -> str | None:
    """Return the smallest matching day value as a canonical string like '30 days'."""
    vals = _parse_duration_days(text, pattern)
    return f"{min(vals)} days" if vals else None


_DESTRUCTION_DAYS_RE = re.compile(
    r"certificate\s+of\s+(?:data\s+)?destruction\s+within\s+(\d+)\s+(business\s+days?|days?)"
    r"|within\s+(\d+)\s+(business\s+days?|days?)\s+of\s+(?:completing\s+)?(?:deletion|disposal|destruction)",
    re.IGNORECASE,
)
_DELETION_DAYS_RE = re.compile(
    r"within\s+(\d+)\s+(?:calendar\s+)?days?\s+of\s+(?:the\s+)?(?:termination|expiration|expiry)",
    re.IGNORECASE,
)
_BREACH_HOURS_RE = re.compile(
    r"within\s+(\d+)\s+(hour|hours)\s+of\s+(?:discov|becom|detect)",
    re.IGNORECASE,
)
_BREACH_TRIGGER_RE = re.compile(
    r"\b(\d+)\s+hours?\s+of\s+(discovering|becoming\s+aware|detecting)",
    re.IGNORECASE,
)
_CONFIDENTIALITY_SURVIVAL_RE = re.compile(
    r"confidentiality\s+obligations?\s+surviv\w+[^.]+?(\d+)\s+(year|years)",
    re.IGNORECASE,
)
_AUDIT_NOTICE_DAYS_RE = re.compile(
    r"(?:audit\w*\s+\w+\s+)?(\d+)\s+(?:business\s+)?days?\s+(?:written\s+)?notice\s+(?:for\s+audit|before\s+audit|to\s+conduct)",
    re.IGNORECASE,
)
_AUDIT_NOTICE_ALT_RE = re.compile(
    r"right\s+to\s+audit\b[^.]+?upon\s+(\d+)\s+(?:business\s+)?days?\s+(?:written\s+)?notice",
    re.IGNORECASE,
)
_CONVENIENCE_NOTICE_RE = re.compile(
    r"terminat\w+\s+for\s+convenience[^.]+?(?:providing|providing|upon)\s+(\d+)\s+days?\s+(?:prior\s+|advance\s+)?written\s+notice"
    r"|(\d+)\s+days?\s+(?:prior\s+|advance\s+)?written\s+notice\s+to\s+the\s+other\s+party",
    re.IGNORECASE,
)


def _extract_field_value(text: str, field_name: str) -> str | None:
    """Extract a canonical field value from raw text. Returns None if field not found."""
    lower = text.lower()
    if field_name == "data_deletion_timeline":
        matches = _DELETION_DAYS_RE.findall(text)
        if matches:
            return f"{min(int(m) for m in matches)} days"
    elif field_name == "cert_of_destruction_days":
        m = _DESTRUCTION_DAYS_RE.search(text)
        if m:
            days = m.group(1) or m.group(3)
            unit = (m.group(2) or m.group(4) or "days").lower()
            label = "business days" if "business" in unit else "days"
            return f"{days} {label}"
    elif field_name == "breach_notification_hours":
        m = _BREACH_HOURS_RE.search(text)
        if m:
            return f"{m.group(1)} hours"
        # fallback: any "N hours of discovering/becoming aware"
        m = _BREACH_TRIGGER_RE.search(text)
        if m:
            return f"{m.group(1)} hours ({m.group(2)})"
    elif field_name == "breach_notification_trigger":
        m = _BREACH_TRIGGER_RE.search(text)
        if m:
            trigger = m.group(2).lower().strip()
            # normalise synonyms
            if "discover" in trigger:
                return "discovering"
            if "aware" in trigger:
                return "becoming aware"
            return trigger
    elif field_name == "confidentiality_survival_years":
        m = _CONFIDENTIALITY_SURVIVAL_RE.search(text)
        if m:
            return f"{m.group(1)} years"
    elif field_name == "audit_notice_days":
        for pattern in (_AUDIT_NOTICE_DAYS_RE, _AUDIT_NOTICE_ALT_RE):
            m = pattern.search(text)
            if m:
                val = next((g for g in m.groups() if g), None)
                if val:
                    return f"{val} days"
    elif field_name == "termination_convenience_days":
        m = _CONVENIENCE_NOTICE_RE.search(text)
        if m:
            val = m.group(1) or m.group(2)
            if val:
                return f"{val} days"
    elif field_name == "liability_cap_exclusions":
        excl_signal = (
            "except" in lower or "exclud" in lower
            or "does not apply" in lower or "shall not be subject" in lower
            or "not subject to" in lower
        )
        # Require liability/damages context to avoid matching confidentiality-exception clauses
        is_liability_context = "liable" in lower or "liability" in lower or "damages" in lower
        parts: list[str] = []
        if excl_signal and is_liability_context:
            if "confidentiality" in lower or "article 5" in lower:
                parts.append("confidentiality")
            if "intellectual property" in lower or "ip infringement" in lower:
                parts.append("ip_infringement")
            if "gross negligence" in lower or "wilful misconduct" in lower or "willful misconduct" in lower:
                parts.append("gross_negligence")
        # DPA-style: deliberate violation not subject to aggregate cap
        if ("deliberate" in lower or "intentional violation" in lower) and (
            "not subject to" in lower or "shall not be subject" in lower or "does not apply" in lower
        ):
            parts.append("deliberate_dpa_violation")
        # Data-breach enhanced cap (greater-of clause)
        if ("data breach" in lower or "data protection" in lower) and excl_signal and is_liability_context:
            parts.append("data_breach")
        return "+".join(sorted(parts)) if parts else None
    return None


def _cross_document_field_audit(
    chunks: list[DocumentChunk],
    document_lookup: dict[str, Document],
    all_package_chunks: list[DocumentChunk],
) -> list[dict]:
    """Systematically extract named fields from each document type and flag mismatches."""
    conflicts: list[dict] = []

    # Fields to audit: (field_id, human_title, severity, expected_same_across_docs)
    AUDIT_FIELDS = [
        ("data_deletion_timeline",         "Post-Termination Data Deletion Timeline",    Severity.HIGH,     True),
        ("cert_of_destruction_days",       "Certificate of Destruction Timeline",         Severity.LOW,      True),
        ("breach_notification_hours",      "Breach Notification Timeline",                Severity.HIGH,     True),
        ("breach_notification_trigger",    "Breach Notification Trigger Wording",         Severity.MEDIUM,   True),
        ("confidentiality_survival_years", "Confidentiality Obligation Survival Period",  Severity.MEDIUM,   True),
        ("audit_notice_days",              "Standard Audit Notice Period",                Severity.MEDIUM,   True),
        ("termination_convenience_days",   "Termination-for-Convenience Notice Period",   Severity.CRITICAL, True),
        ("liability_cap_exclusions",       "Liability Cap Exclusion Set",                 Severity.HIGH,     True),
    ]

    for field_id, field_title, severity, expect_same in AUDIT_FIELDS:
        # Map doc_type → best chunk + extracted value
        doc_type_values: dict[str, tuple[str, DocumentChunk]] = {}

        for chunk in all_package_chunks:
            doc_type = chunk.document_type or "unknown"
            if doc_type in doc_type_values:
                continue  # already have a value for this doc type
            val = _extract_field_value(chunk.text, field_id)
            if val:
                doc_type_values[doc_type] = (val, chunk)

        if len(doc_type_values) < 2:
            continue  # need at least two docs to have a conflict

        # Normalise: strip whitespace for comparison
        unique_values = {v for v, _ in doc_type_values.values()}
        if len(unique_values) <= 1:
            continue  # consistent — no conflict

        # Find the two chunks with the most different values to use as citations
        items = sorted(doc_type_values.items())  # deterministic ordering
        left_doc, (left_val, left_chunk) = items[0]
        # Pick the item with a different value
        right_item = next(
            ((dt, (v, c)) for dt, (v, c) in items[1:] if v != left_val),
            items[1] if len(items) > 1 else None,
        )
        if right_item is None:
            continue
        right_doc, (right_val, right_chunk) = right_item

        # Skip if left and right are actually the same value
        if left_val == right_val:
            continue

        # Build human-readable summary
        all_values_str = "; ".join(
            f"{dt.upper()}: {v}" for dt, (v, _) in sorted(doc_type_values.items())
        )
        conflicts.append(
            {
                "conflict_id": f"cnf_{uuid4().hex[:12]}",
                "title": f"Conflict: {field_title}",
                "summary": (
                    f"Conflicting values found for '{field_title}' across uploaded documents. "
                    f"Values per document: {all_values_str}. "
                    f"Procurement teams should ensure all documents are aligned before execution."
                ),
                "left_citation": _serialize_citation(left_chunk, document_lookup),
                "right_citation": _serialize_citation(right_chunk, document_lookup),
                "severity": severity.value,
            }
        )

    return conflicts


def build_report(db: Session, package: VendorPackage, playbook_version_id: str) -> dict:
    requirements = db.scalars(
        select(Requirement).where(Requirement.playbook_version_id == playbook_version_id).order_by(Requirement.page_number)
    ).all()
    requirements = select_actionable_requirements(requirements)
    documents = db.scalars(
        select(Document).where(Document.owner_type == "package", Document.owner_id == package.id)
    ).all()
    document_lookup = {document.id: document for document in documents}
    chunks = db.scalars(
        select(DocumentChunk).where(DocumentChunk.owner_type == "package", DocumentChunk.owner_id == package.id)
    ).all()
    chunk_lookup = {chunk.id: chunk for chunk in chunks}

    total = len(requirements)
    log.info("[compliance] Starting analysis: %d requirements, %d chunks, package=%s",
             total, len(chunks), package.id)

    pre_findings: list[dict] = []
    conflicts: list[dict] = []
    summary_counter: Counter[str] = Counter()

    # ── Phase 1+2: sequential vector query + rule analysis ────────────────────
    # One embed_query call per requirement, paced by the global rate limiter.
    # No threading — avoids thundering-herd 429s on the free tier.
    for idx, requirement in enumerate(requirements, start=1):
        requirement_query = _build_query_text(requirement)
        short_title = requirement.title[:60] if requirement.title else requirement_query[:60]
        log.info("[compliance] Req %d/%d — embed+query: %r", idx, total, short_title)

        expected_documents = set(requirement.expected_documents_json or [])
        query_where = _build_query_where(package.id, expected_documents)

        candidate_results = vector_store.query(
            owner_type="vendor",
            query_text=requirement_query,
            where=query_where,
            top_k=6,
        )
        if not candidate_results and "document_type" in query_where:
            candidate_results = vector_store.query(
                owner_type="vendor",
                query_text=requirement_query,
                where={"owner_id": package.id},
                top_k=6,
            )

        requirement_keywords = requirement.keywords_json or []

        # ── Chunk retrieval: vector candidates + section-targeted injection ──────
        # Phase A: score vector candidates with doc-type affinity and section boost.
        scored_candidates: list[tuple[float, DocumentChunk]] = []
        vector_candidate_ids: set[str] = set()
        for result in candidate_results:
            chunk_id = result["metadata"].get("chunk_id")
            if chunk_id in chunk_lookup:
                chunk = chunk_lookup[chunk_id]
                vector_candidate_ids.add(chunk_id)
                section_boost = _section_relevance_boost(requirement.requirement_text, chunk.section_name)
                doc_affinity = _doc_type_affinity(requirement.requirement_text, chunk.document_type)
                adjusted_score = min(1.0, result["score"] * doc_affinity + section_boost)
                relevance = _score_relevance(requirement_query, requirement_keywords, chunk.text, adjusted_score)
                if relevance > 0.0:
                    scored_candidates.append((relevance, chunk))

        # Phase B: section-targeted injection — ensure on-topic sections appear even
        # if the vector search returned only off-topic chunks (e.g. DPA Art.1 instead of Art.9).
        for chunk in chunks:
            if chunk.id in vector_candidate_ids:
                continue
            section_boost = _section_relevance_boost(requirement.requirement_text, chunk.section_name)
            if section_boost > 0.0:
                lexical = _score_lexical(requirement_query, chunk.text)
                relevance = _score_relevance(
                    requirement_query, requirement_keywords, chunk.text, min(1.0, lexical + section_boost)
                )
                if relevance > 0.0:
                    scored_candidates.append((relevance, chunk))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        matched_chunks = [c for _, c in scored_candidates[:6]]
        retrieval_scores = [s for s, _ in scored_candidates[:6]]

        if not matched_chunks:
            lexical_scored = [
                (chunk, _score_relevance(requirement_query, requirement_keywords, chunk.text, _score_lexical(requirement_query, chunk.text)))
                for chunk in chunks
            ]
            lexical_ranked = sorted((item for item in lexical_scored if item[1] > 0.0), key=lambda item: item[1], reverse=True)[:6]
            matched_chunks = [chunk for chunk, _ in lexical_ranked]
            retrieval_scores = [score for _, score in lexical_ranked]

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

        referenced_document_types = {chunk.document_type for chunk in matched_chunks}
        document_scope_coverage = 1.0 if not expected_documents else len(referenced_document_types & expected_documents) / len(expected_documents)
        retrieval_score = max(retrieval_scores) if retrieval_scores else 0.0
        extraction_score = min(1.0, 0.55 + (0.07 * len(matched_chunks))) if matched_chunks else 0.15
        grounding_score = min(0.95, 0.25 + (retrieval_score * 0.7)) if matched_chunks else 0.2
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
        elif "vendor risk register" in lower_requirement or ("exception" in lower_requirement and "remediation" in lower_requirement):
            remediation_values = []
            for chunk in matched_chunks:
                remediation_values.extend(_parse_duration_days(chunk.text, REMEDIATION_RE))
            lowered_chunks = [chunk.text.lower() for chunk in matched_chunks]
            has_exception_log = any(
                token in text
                for text in lowered_chunks
                for token in ["exception log", "approved exception", "deviation is recorded", "exception reference"]
            )
            has_register_entry = any("vendor risk register" in text for text in lowered_chunks)
            within_limit = any(value <= 180 for value in remediation_values)
            if has_register_entry and (within_limit or not remediation_values):
                rule_completion = 1.0
                search_summary = "The uploaded package includes direct Vendor Risk Register evidence for the documented exception."
            elif has_exception_log:
                rule_completion = 0.58
                search_summary = "The uploaded package references an approved exception log or documented deviation, but the Vendor Risk Register entry itself was not provided."
            else:
                rule_completion = 0.0
                search_summary = "No Vendor Risk Register entry or equivalent exception documentation was found in the uploaded package."
            fallback_summary = "The requirement expects explicit exception documentation and a remediation timeline, not generic MSA boilerplate."
        elif any(token in lower_requirement for token in ["hierarchy of documents", "order of precedence", "entire agreement", "incorporated"]):
            lowered_chunks = [chunk.text.lower() for chunk in matched_chunks]
            has_playbook_integration = any(
                "playbook" in text and ("incorporated" in text or "entire agreement" in text or "reference" in text)
                for text in lowered_chunks
            )
            has_precedence_language = any(
                token in text
                for text in lowered_chunks
                for token in ["order of precedence", "supersedes", "entire agreement"]
            )
            rule_completion = 1.0 if has_playbook_integration or has_precedence_language else 0.0
            if rule_completion >= 1.0:
                search_summary = "Integration and precedence language was found in the vendor package, including incorporation of the Playbook by reference."
            else:
                search_summary = "No integration or precedence clause matching the Playbook hierarchy requirement was found in the uploaded package."
            fallback_summary = "The requirement expects the vendor contract stack to incorporate or respect the Playbook's order of precedence."
        elif "data subject" in lower_requirement or (
            "erasure" in lower_requirement and "portability" in lower_requirement
        ):
            # ── Fix 3: DSR with numeric response-time comparison ──────────────────
            dsr_types = ["access", "rectification", "erasure", "portability", "restriction"]
            found_rights = sum(1 for right in dsr_types if right in combined_text.lower())
            rights_coverage = found_rights / len(dsr_types)
            req_hours_list = _parse_duration_hours(requirement.requirement_text, WITHIN_TIME_RE)
            max_req_hours = max(req_hours_list) if req_hours_list else 72.0
            evidence_hours: list[float] = []
            for chunk in matched_chunks:
                evidence_hours.extend(_parse_duration_hours(chunk.text, WITHIN_TIME_RE))
            time_met = bool(evidence_hours) and min(evidence_hours) <= max_req_hours
            has_technical_capability = any(
                kw in combined_text.lower()
                for kw in ["export", "permanently delet", "technically capable", "machine-readable",
                           "processor shall provide", "data subject request", "identifying all"]
            )
            if time_met and rights_coverage >= 0.8:
                rule_completion = 1.0
                hrs = min(evidence_hours)
                search_summary = (
                    f"Data subject rights fully evidenced: {found_rights}/5 right types confirmed and "
                    f"vendor commits to \u2264{hrs:.0f}-hour response (required \u2264{max_req_hours:.0f}h)."
                )
            elif rights_coverage >= 0.6 and (time_met or has_technical_capability):
                rule_completion = 0.72 + (0.13 if time_met else 0.0)
                if not time_met and not evidence_hours:
                    search_summary = (
                        f"{found_rights}/5 data subject right types found with technical capability, "
                        f"but no explicit \u2264{max_req_hours:.0f}-hour response commitment detected."
                    )
                else:
                    hrs_str = f"{min(evidence_hours):.0f}h" if evidence_hours else "unknown"
                    search_summary = f"Partial DSR coverage: {found_rights}/5 rights; vendor response time {hrs_str}."
            else:
                rule_completion = rights_coverage * 0.5
                search_summary = (
                    f"Limited DSR evidence: {found_rights}/5 right types found. "
                    f"No explicit {max_req_hours:.0f}-hour response commitment detected."
                )
            fallback_summary = (
                f"Requirement expects all 5 data subject rights supported within \u2264{max_req_hours:.0f}h "
                f"of Company notification, with documented technical capability to identify, export, and delete."
            )
        elif (
            "destroy" in lower_requirement
            or "nist sp 800" in lower_requirement
            or ("certificate" in lower_requirement and "destruction" in lower_requirement)
        ):
            # ── Fix 2: Post-termination deletion — 30-day window, NIST 800-88, cert ──
            # Scan all DPA chunks for comprehensive evidence (requirements span sub-sections).
            dpa_chunks = [c for c in chunks if (c.document_type or "").lower() == "dpa"]
            evidence_pool = list({c.id: c for c in matched_chunks + dpa_chunks}.values())
            within_day_vals = [
                int(amt)
                for c in evidence_pool
                for amt, unit in WITHIN_TIME_RE.findall(c.text)
                if unit.lower() in ("day", "days")
            ]
            has_30day_window = any(v <= 30 for v in within_day_vals)
            has_nist = any("nist" in c.text.lower() and "800" in c.text for c in evidence_pool)
            has_cert_destruction = any(
                kw in c.text.lower()
                for c in evidence_pool
                for kw in ["certificate of data destruction", "certificate of destruction", "signed certificate"]
            )
            has_destroy_clause = any(
                kw in c.text.lower()
                for c in evidence_pool
                for kw in ["certifiably destroy", "destroy all", "return all personal data",
                           "return all company data", "deletion and return"]
            )
            if has_30day_window and has_nist and has_cert_destruction:
                rule_completion = 1.0
                search_summary = (
                    "Post-termination deletion fully evidenced: 30-day timeline, NIST SP 800-88 standards, "
                    "and signed Certificate of Destruction all found in the DPA."
                )
            elif has_30day_window and has_nist:
                rule_completion = 0.85
                search_summary = (
                    "Post-termination deletion: 30-day window and NIST SP 800-88 confirmed, but explicit "
                    "Certificate of Destruction language was not located in retrieved text."
                )
            elif has_30day_window or has_destroy_clause:
                rule_completion = 0.60
                search_summary = (
                    "Post-termination deletion commitment found (30-day window or destroy clause), but "
                    "NIST SP 800-88 media sanitisation standards or destruction certificate not fully evidenced."
                )
            else:
                rule_completion = 0.0
                search_summary = (
                    "No explicit post-termination deletion timeline found. Expected a 30-day destruction window, "
                    "NIST SP 800-88 compliance, and a signed Certificate of Destruction in the DPA."
                )
            fallback_summary = (
                "Requirement expects: (1) \u226430-day post-termination destruction of all Company Data, "
                "(2) NIST SP 800-88 Rev. 1 media sanitization standards, and "
                "(3) a signed Certificate of Data Destruction."
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
            # ── Fix 1 & 5: Broadened retention detection using section-aware parsing ──
            # BROAD_RETENTION_RE captures "7 years from fiscal year end", "90 days", etc.
            # that the original strict RETENTION_RE missed.
            retention_specific: list[int] = []
            for chunk in matched_chunks:
                strict_vals = _parse_duration_days(chunk.text, RETENTION_RE)
                if strict_vals:
                    retention_specific.extend(strict_vals)
                elif any(
                    kw in (chunk.section_name or "").lower()
                    for kw in ["retention", "deletion", "article 9", "9.1", "9.2", "9.3"]
                ):
                    # Confirmed retention section — safe to use the broad pattern.
                    retention_specific.extend(_parse_duration_days(chunk.text, BROAD_RETENTION_RE))
            # Keyword-presence fallback: specific DRS phrases that only appear in Art. 9.
            has_retention_clause = any(
                kw in combined_text.lower()
                for kw in [
                    "data retention schedule", "retention schedule applicability",
                    "retention periods apply", " drs ", "30 calendar days",
                    "90 days rolling", "certificate of data destruction",
                ]
            )
            rule_completion = 1.0 if retention_specific or has_retention_clause else 0.0
            if retention_specific or has_retention_clause:
                search_summary = "Retention schedule or deletion timeline evidence found in the vendor's DPA."
            else:
                search_summary = "No retention schedule or deletion timeline was found across the uploaded package documents."
            fallback_summary = "The requirement expects a documented retention or deletion timeline matching the Company's Data Retention Schedule (DRS) categories."
        elif "certification" in lower_requirement or "soc 2" in lower_requirement or "iso 27001" in lower_requirement:
            # ── Fix 6: Certification with cert-expiry vs contract-term comparison ──
            certifications = sorted(set(cert_values))
            mentioned_in_msa = any(
                chunk.document_type == "msa"
                and any(cert.lower() in chunk.text.lower() for cert in certifications)
                for chunk in matched_chunks
            )
            rule_completion = (
                1.0 if certifications and (mentioned_in_msa or "msa" not in lower_requirement)
                else 0.45 if certifications
                else 0.0
            )
            # Scan all package chunks for cert-expiry and contract-term dates.
            cert_expiry: datetime | None = None
            all_effective_dates: list[datetime] = []
            all_term_months: list[int] = []
            renewal_committed = False
            for c in chunks:
                for date_str in CERT_VALID_THROUGH_RE.findall(c.text):
                    parsed = _parse_cert_date(date_str)
                    if parsed and (cert_expiry is None or parsed < cert_expiry):
                        cert_expiry = parsed
                for date_str in CONTRACT_EFFECTIVE_DATE_RE.findall(c.text):
                    parsed = _parse_cert_date(date_str)
                    if parsed:
                        all_effective_dates.append(parsed)
                for months_str in CONTRACT_TERM_MONTHS_RE.findall(c.text):
                    all_term_months.append(int(months_str))
                if any(kw in c.text.lower() for kw in ["recertif", "renewed certificate", "renewal audit"]):
                    renewal_committed = True
            contract_end: datetime | None = None
            if all_effective_dates and all_term_months:
                earliest_eff = min(all_effective_dates)
                longest_term = max(all_term_months)
                contract_end = _add_months(earliest_eff, longest_term)
            if certifications and cert_expiry and contract_end and cert_expiry < contract_end:
                if renewal_committed:
                    rule_completion = min(rule_completion, 0.72)
                    search_summary = (
                        f"Certifications found ({', '.join(certifications)}), but certificate expires "
                        f"{cert_expiry.strftime('%B %d, %Y')}, before contract end "
                        f"({contract_end.strftime('%B %d, %Y')}). Vendor commits to recertification."
                    )
                else:
                    rule_completion = min(rule_completion, 0.60)
                    search_summary = (
                        f"Certifications found ({', '.join(certifications)}), but certificate expires "
                        f"{cert_expiry.strftime('%B %d, %Y')}, before contract end "
                        f"({contract_end.strftime('%B %d, %Y')}). No confirmed renewal found."
                    )
            elif certifications and cert_expiry and contract_end:
                search_summary = (
                    f"Certifications found ({', '.join(certifications)}). "
                    f"Certificate valid through {cert_expiry.strftime('%B %d, %Y')}, covering the full contract term."
                )
            elif certifications and not mentioned_in_msa and "msa" in lower_requirement:
                search_summary = "Security certifications were found, but the MSA does not appear to reference them."
            elif certifications:
                search_summary = f"Detected certifications in the package: {', '.join(certifications)}."
            else:
                search_summary = "No qualifying certification evidence was found in the uploaded package."
            fallback_summary = "The package was checked for active certifications. Certificate validity period is compared against the contract term."
        elif (
            "tls" in lower_requirement
            or "aes-256" in lower_requirement
            or (
                "encrypt" in lower_requirement
                and (
                    "transit" in lower_requirement
                    or "key management" in lower_requirement
                    or "key rotation" in lower_requirement
                )
            )
        ):
            # ── Fix 4: Encryption standards — explicit sub-requirement scoring ────
            has_tls_modern = any(
                "tls 1.2" in c.text.lower() or "tls 1.3" in c.text.lower()
                for c in matched_chunks
            )
            has_tls_old_disabled = any(
                ("tls 1.0" in c.text.lower() or "1.0 and" in c.text.lower())
                and ("disabled" in c.text.lower() or "prohibited" in c.text.lower())
                for c in matched_chunks
            )
            has_aes256 = any(
                "aes-256" in c.text.lower() or "aes 256" in c.text.lower()
                for c in matched_chunks
            )
            has_key_rotation = any(
                any(kw in c.text.lower() for kw in
                    ["keys rotated", "rotated annually", "annual rotation", "key rotation", "annually"])
                and "key" in c.text.lower()
                for c in matched_chunks
            )
            has_key_separation = any(
                any(kw in c.text.lower() for kw in
                    ["stored separately", "managed separately", "key custod", "2-person rule"])
                for c in matched_chunks
            )
            sub_reqs_met = sum([has_tls_modern, has_aes256, has_key_rotation])
            rule_completion = sub_reqs_met / 3.0
            if has_tls_old_disabled:
                rule_completion = min(1.0, rule_completion + 0.05)
            if has_key_separation:
                rule_completion = min(1.0, rule_completion + 0.05)
            evidence_parts = []
            if has_tls_modern:
                evidence_parts.append("TLS 1.2+/1.3")
            if has_tls_old_disabled:
                evidence_parts.append("TLS 1.0/1.1 disabled")
            if has_aes256:
                evidence_parts.append("AES-256")
            if has_key_rotation:
                evidence_parts.append("annual key rotation")
            if has_key_separation:
                evidence_parts.append("key separation")
            if rule_completion >= 0.95:
                search_summary = "Full encryption standards compliance: " + ", ".join(evidence_parts) + "."
            elif rule_completion >= 0.6:
                search_summary = (
                    f"Partial encryption compliance ({sub_reqs_met}/3 sub-requirements met): "
                    + ", ".join(evidence_parts) + "."
                )
            else:
                found_str = ", ".join(evidence_parts) if evidence_parts else "none"
                search_summary = (
                    f"Insufficient encryption evidence. Required: TLS 1.2+, AES-256, annual key rotation. "
                    f"Found: {found_str}."
                )
            fallback_summary = (
                "Requirement checks for TLS 1.2+ (TLS 1.0/1.1 prohibited), AES-256 at rest, "
                "and annual key rotation with key management separate from encrypted data."
            )
        else:
            keyword_hits = sum(1 for keyword in requirement_keywords if keyword in combined_text.lower())
            keyword_total = max(1, len(requirement_keywords))
            rule_completion = min(1.0, max(retrieval_score, keyword_hits / keyword_total) * max(0.5, document_scope_coverage))
            search_summary = "Compared requirement keywords and related chunk evidence across the uploaded documents."
            fallback_summary = "The system gathered the most relevant package excerpts for this requirement and measured evidence coverage."

        has_relevant_evidence = retrieval_score >= MIN_RELEVANT_RETRIEVAL
        status = _infer_status(rule_completion, retrieval_score, has_conflict, bool(matched_chunks), has_relevant_evidence)
        if status == FindingStatus.MISSING and not has_conflict:
            vendor_citations = []
            rule_completion = 0.0
            grounding_score = min(grounding_score, 0.3)
            search_summary = (
                "No relevant vendor clause was found for this requirement. Retrieved text did not match the required subject closely enough "
                "to support a compliance decision."
            )
            fallback_summary = "The uploaded package does not provide enough relevant evidence to verify this requirement."
        if status == FindingStatus.CONFLICT:
            severity = Severity.CRITICAL
        else:
            severity = Severity(requirement.severity)
        confidence_breakdown = ConfidenceBreakdown(
            extraction=min(1.0, extraction_score),
            retrieval=min(1.0, max(0.0, retrieval_score)),
            grounding=grounding_score,
            rule_completion=min(1.0, max(0.0, rule_completion)),
        )
        confidence = (
            confidence_breakdown.extraction * 0.2
            + confidence_breakdown.retrieval * 0.25
            + confidence_breakdown.grounding * 0.25
            + confidence_breakdown.rule_completion * 0.3
        )
        if status == FindingStatus.MISSING:
            confidence = min(confidence, 0.35)
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
        summary_counter[status.value] += 1

        log.info("[compliance] Req %d/%d — status=%s rule_completion=%.2f retrieval=%.2f",
                 idx, total, status.value, rule_completion, retrieval_score)

        pre_findings.append(
            {
                "finding_id": f"fdg_{uuid4().hex[:12]}",
                "title": title,
                "category": requirement.category,
                "severity": severity.value,
                "status": status.value,
                "policy_citation": policy_citation,
                "vendor_citations": vendor_citations,
                "confidence": round(confidence, 2),
                "confidence_breakdown": confidence_breakdown.model_dump(),
                "search_summary": search_summary,
                "_req_text": requirement.requirement_text,
                "_evidence_text": evidence_text,
                "_fallback_summary": fallback_summary,
            }
        )

    log.info("[compliance] All %d requirements evaluated. Generating AI summaries...", total)

    # ── Phase 3: sequential AI summaries (Gemini Flash) ───────────────────────
    summaries: list[str] = []
    for idx, pf in enumerate(pre_findings, start=1):
        log.info("[compliance] Summary %d/%d — %r", idx, total, pf["title"][:60])
        summaries.append(
            gemini_service.summarize_finding(pf["_req_text"], pf["_evidence_text"], pf["_fallback_summary"])
        )

    log.info("[compliance] Done. %d findings, %d conflicts.", len(pre_findings), len(conflicts))

    # ── Phase 4: assemble final findings ──────────────────────────────────────
    findings: list[dict] = [
        {k: v for k, v in pf.items() if not k.startswith("_")} | {"summary": summary}
        for pf, summary in zip(pre_findings, summaries)
    ]

    global_conflicts = _detect_global_conflicts(chunks, document_lookup)
    field_conflicts = _cross_document_field_audit(chunks, document_lookup, list(chunks))
    existing_pairs = {
        (conflict["left_citation"]["source_id"], conflict["right_citation"]["source_id"]) for conflict in conflicts
    }
    for conflict in global_conflicts + field_conflicts:
        pair = (conflict["left_citation"]["source_id"], conflict["right_citation"]["source_id"])
        if pair not in existing_pairs:
            conflicts.append(conflict)
            existing_pairs.add(pair)

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