from __future__ import annotations

import re
from typing import Iterable

MAX_ANALYZED_REQUIREMENTS = 60

OBLIGATION_RE = re.compile(r"\b(must not|may not|must|shall|required to|is required to|required|mandatory)\b", re.IGNORECASE)
POLICY_REQUIREMENT_RE = re.compile(r"policy requirement", re.IGNORECASE)
# Explicitly vendor-directed obligations: strongest signal
VENDOR_OBLIGATION_RE = re.compile(
    r"\bvendors?\s+(must\s+not|may\s+not|must|shall|are\s+required\s+to|are\s+prohibited|will)\b"
    r"|\bmust\s+be\s+(provided|submitted|maintained|documented|tested|completed|obtained|notifi|updated|reviewed|trained|available|conducted|reported)\b"
    r"|\bshall\s+be\s+(provided|submitted|maintained|documented|completed|tested|obtained|conducted|made\s+available)\b"
    r"|\bvendors?\s+are\s+(required|prohibited|obligated)\b",
    re.IGNORECASE,
)
# Exclude sentences that are company/mutual obligations, not vendor-specific
COMPANY_MUTUAL_EXCLUSION_RE = re.compile(
    r"\bthe\s+company\s+shall\b"
    r"|\beither\s+party\s+shall\b"
    r"|\bparties\s+shall\b"
    r"|\bcontroller\s+shall\b"
    r"|\bthe\s+company\s+will\b"
    r"|\bwe\s+shall\b"
    r"|\bcompany(?:'s)?\s+(?:aggregate\s+)?liability\s+is\s+capped\b",
    re.IGNORECASE,
)
MEASURABLE_RE = re.compile(
    r"(\$\s?\d|\b\d+\s*(?:day|days|hour|hours|month|months|year|years|business\s+days?)\b|\b(?:soc\s*2|iso\s*27001|gdpr|ccpa|nist|tls|aes-256|mfa|sccs|fedramp|hitrust|rto|rpo)\b)",
    re.IGNORECASE,
)
GENERIC_START_RE = re.compile(
    r"^(this\s+playbook\s+establishes|this\s+procurement\s+policy\s+playbook\s+establishes|this\s+playbook\s+applies|the\s+playbook\s+applies|where\s+a\s+vendor\s+engagement\s+involves)",
    re.IGNORECASE,
)
DEFINITION_RE = re.compile(r'^"?[A-Za-z][^\"]{0,80}"?\s+means\b', re.IGNORECASE)

CHECKABLE_HINTS = {
    "access",
    "additional insured",
    "aes-256",
    "agreement",
    "approval",
    "audit",
    "breach",
    "certificate",
    "certification",
    "coverage",
    "cross-border",
    "data processing agreement",
    "deletion",
    "dpa",
    "encryption",
    "entire agreement",
    "exception",
    "exception log",
    "export",
    "fedramp",
    "gdpr",
    "hierarchy",
    "incorporated",
    "indemnify",
    "insurance",
    "iso 27001",
    "liability",
    "mfa",
    "msa",
    "notice",
    "order of precedence",
    "pci",
    "playbook",
    "privacy",
    "register",
    "remediation",
    "retention",
    "risk",
    "security",
    "soc 2",
    "subcontract",
    "termination",
    "timeline",
    "tls",
    "vendor risk register",
}


def normalize_requirement_text(text: str) -> str:
    return " ".join(text.split())


def _section_code(section_name: str | None) -> str:
    match = re.match(r"^(\d+(?:\.\d+)*)", section_name or "")
    return match.group(1) if match else ""


def is_actionable_requirement(text: str, section_name: str | None = None) -> bool:
    normalized = normalize_requirement_text(text)
    lower = normalized.lower()
    if len(normalized) < 35:
        return False
    if DEFINITION_RE.search(normalized):
        return False
    if GENERIC_START_RE.search(lower):
        return False
    # Exclude company / mutual obligations — these aren't vendor compliance requirements
    if COMPANY_MUTUAL_EXCLUSION_RE.search(lower):
        return False

    section_code = _section_code(section_name)
    if section_code in {"1.1", "1.2"}:
        return False
    if section_code.startswith("2."):
        return False

    has_obligation = bool(OBLIGATION_RE.search(lower) or POLICY_REQUIREMENT_RE.search(lower))
    if not has_obligation:
        return False

    # Explicit vendor obligation ("Vendor must/shall", "must be maintained") passes
    # without requiring a separate measurable signal — the verb is the signal.
    if VENDOR_OBLIGATION_RE.search(lower):
        return True

    # For general obligation verbs (shall/required) confirm there's a checkable topic.
    has_checkable_signal = bool(MEASURABLE_RE.search(lower)) or any(token in lower for token in CHECKABLE_HINTS)
    return has_checkable_signal


def build_requirement_aliases(text: str, section_name: str | None = None) -> list[str]:
    lower = normalize_requirement_text(text).lower()
    aliases: list[str] = []

    if "vendor risk register" in lower or "exception" in lower or "remediation timeline" in lower:
        aliases.extend([
            "exception log",
            "approved exception",
            "documented deviation",
            "vendor risk register",
            "remediation timeline",
        ])

    if any(token in lower for token in ["hierarchy of documents", "order of precedence", "entire agreement", "incorporated"]):
        aliases.extend([
            "entire agreement",
            "integration clause",
            "incorporated herein by reference",
            "order of precedence",
            "supersedes",
        ])

    if "termination" in lower and "notice" in lower:
        aliases.extend([
            "termination notice",
            "written notice",
            "termination for convenience",
            "days notice",
        ])

    if "insurance" in lower or "coverage" in lower or "liability" in lower:
        aliases.extend([
            "insurance certificate",
            "coverage limits",
            "additional insured",
        ])

    if "dpa" in lower or "data processing" in lower:
        aliases.extend([
            "data processing agreement",
            "article 28",
            "privacy addendum",
        ])

    if "soc 2" in lower or "iso 27001" in lower or "certification" in lower:
        aliases.extend([
            "soc 2 type ii",
            "iso 27001",
            "audit report",
        ])

    if section_name:
        aliases.append(section_name)

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = alias.lower().strip()
        if key and key not in seen:
            deduped.append(alias)
            seen.add(key)
    return deduped


def expand_keywords(text: str, base_keywords: Iterable[str], section_name: str | None = None) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for token in list(base_keywords) + build_requirement_aliases(text, section_name):
        normalized = token.strip().lower()
        if normalized and normalized not in seen:
            expanded.append(normalized)
            seen.add(normalized)
    return expanded


def requirement_priority(text: str, section_name: str | None = None) -> int:
    lower = normalize_requirement_text(text).lower()
    score = 0
    if POLICY_REQUIREMENT_RE.search(lower):
        score += 6
    if VENDOR_OBLIGATION_RE.search(lower):
        score += 3
    if MEASURABLE_RE.search(lower):
        score += 2
    if any(token in lower for token in [
        "vendor risk register", "entire agreement", "termination", "insurance",
        "retention", "soc 2", "dpa", "breach", "encryption", "certification",
        "liability", "subcontract", "audit",
    ]):
        score += 2
    high_priority_sections = {
        "1.3", "3.2", "4.1", "5.1", "5.4", "5.5", "5.6", "6.1", "6.5",
        "7.1", "8.1", "8.2", "9.1", "12.1", "13.1", "14.1", "14.2", "15.1",
    }
    if section_name and _section_code(section_name) in high_priority_sections:
        score += 2
    return score


def select_actionable_requirements(requirements: list, limit: int = MAX_ANALYZED_REQUIREMENTS) -> list:
    actionable = [
        requirement
        for requirement in requirements
        if is_actionable_requirement(requirement.requirement_text, getattr(requirement, "section_name", None))
    ]
    ranked = actionable or list(requirements)
    ranked = sorted(
        ranked,
        key=lambda requirement: (
            -requirement_priority(requirement.requirement_text, getattr(requirement, "section_name", None)),
            getattr(requirement, "page_number", 0),
            getattr(requirement, "id", ""),
        ),
    )
    selected = ranked[:limit]
    return sorted(
        selected,
        key=lambda requirement: (
            getattr(requirement, "page_number", 0),
            getattr(requirement, "section_name", "") or "",
            getattr(requirement, "id", ""),
        ),
    )