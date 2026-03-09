import type { Finding } from "@/lib/api";

const statusLabels: Record<Finding["status"], string> = {
  compliant: "Compliant",
  partial: "Partial",
  non_compliant: "Non-compliant",
  missing: "Missing",
  conflict: "Conflict",
};

interface FindingCardProps {
  finding: Finding;
}

export function FindingCard({ finding }: FindingCardProps) {
  return (
    <article className={`finding-card severity-${finding.severity}`}>
      <div className="finding-meta-row">
        <span className="badge">{finding.category}</span>
        <span className="badge muted">{statusLabels[finding.status]}</span>
        <span className="confidence">Confidence {(finding.confidence * 100).toFixed(0)}%</span>
      </div>
      <h3>{finding.title}</h3>
      <p>{finding.summary}</p>
      <div className="citation-block">
        <span className="eyebrow">Playbook requirement</span>
        <strong>{finding.policy_citation.section}</strong>
        <p>{finding.policy_citation.excerpt}</p>
      </div>
      <div className="citation-block subtle">
        <span className="eyebrow">Search summary</span>
        <p>{finding.search_summary}</p>
      </div>
    </article>
  );
}
