from dataclasses import dataclass

from app.services.requirement_utils import (
    MAX_ANALYZED_REQUIREMENTS,
    build_requirement_aliases,
    is_actionable_requirement,
    select_actionable_requirements,
)


@dataclass
class FakeRequirement:
    id: str
    requirement_text: str
    section_name: str
    page_number: int


def test_purpose_statement_is_not_actionable_requirement() -> None:
    text = (
        'This Procurement Policy Playbook establishes the minimum contractual, operational, and compliance '
        'requirements that every vendor providing goods or services to Greybeard Corporate Solutions must satisfy.'
    )

    assert not is_actionable_requirement(text, "1.1 Purpose")


def test_exception_log_clause_remains_actionable() -> None:
    text = "Exceptions shall be documented in the Vendor Risk Register with a specific remediation timeline not to exceed 180 days."

    assert is_actionable_requirement(text, "3.2 Exceptions and Escalations")
    assert "exception log" in build_requirement_aliases(text, "3.2 Exceptions and Escalations")


def test_select_actionable_requirements_caps_results() -> None:
    requirements = [
        FakeRequirement(
            id=f"req_{index}",
            requirement_text=f"POLICY REQUIREMENT Section {index}: Vendors must maintain SOC 2 Type II evidence within {index + 1} days.",
            section_name=f"6.{index} Security Requirement",
            page_number=index,
        )
        for index in range(MAX_ANALYZED_REQUIREMENTS + 10)  # always exceeds cap
    ]

    selected = select_actionable_requirements(requirements)

    assert len(selected) == MAX_ANALYZED_REQUIREMENTS