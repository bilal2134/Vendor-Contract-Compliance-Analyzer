from __future__ import annotations

import csv
import io
import json

from app.models.entities import Report


def export_report(report: Report, export_format: str) -> tuple[str, str]:
    if export_format == "json":
        return json.dumps(
            {
                "report_id": report.id,
                "package_id": report.package_id,
                "vendor_name": report.vendor_name,
                "playbook_version_id": report.playbook_version_id,
                "summary": report.summary_json,
                "findings": report.findings_json,
                "conflicts": report.conflicts_json,
            },
            indent=2,
        ), "application/json"

    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["finding_id", "title", "category", "severity", "status", "confidence", "policy_section", "vendor_sources"])
        for finding in report.findings_json:
            writer.writerow(
                [
                    finding["finding_id"],
                    finding["title"],
                    finding["category"],
                    finding["severity"],
                    finding["status"],
                    finding["confidence"],
                    finding["policy_citation"].get("section"),
                    "; ".join(citation["source_name"] for citation in finding.get("vendor_citations", [])),
                ]
            )
        return buffer.getvalue(), "text/csv"

    raise ValueError("Unsupported export format")
