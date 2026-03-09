import Link from "next/link";
import { notFound } from "next/navigation";

import { getReport } from "@/lib/api";

export default async function FindingDetailPage({
  params,
}: {
  params: Promise<{ reportId: string; findingId: string }>;
}) {
  const { reportId, findingId } = await params;
  const report = await getReport(reportId).catch(() => null);

  if (!report) {
    notFound();
  }

  const finding = report.findings.find((item) => item.finding_id === findingId);

  if (!finding) {
    notFound();
  }

  return (
    <main className="stack-lg">
      <section className="hero hero-report">
        <span className="kicker">Finding drill-down</span>
        <div className="stack-md">
          <h1>{finding.title}</h1>
          <p>{finding.summary}</p>
        </div>
        <div className="finding-meta-row">
          <span className="badge">{finding.category}</span>
          <span className="badge muted">{finding.status.replaceAll("_", " ")}</span>
          <span className="confidence">Confidence {(finding.confidence * 100).toFixed(0)}%</span>
        </div>
        <div className="actions">
          <Link href={`/reports/${reportId}`} className="button-secondary">
            Back to report
          </Link>
        </div>
      </section>

      <section className="grid grid-2">
        <article className="panel stack-md">
          <div>
            <span className="eyebrow">Policy evidence</span>
            <h2>{finding.policy_citation.section}</h2>
          </div>
          <p>{finding.policy_citation.excerpt}</p>
          <div className="muted-surface">
            <strong>{finding.policy_citation.source_name}</strong>
            <p>
              Page {finding.policy_citation.page ?? "n/a"} · {finding.policy_citation.locator ?? "no locator"}
            </p>
          </div>
        </article>

        <article className="panel stack-md">
          <div>
            <span className="eyebrow">Vendor evidence</span>
            <h2>What the package says</h2>
          </div>
          {finding.vendor_citations.length === 0 ? (
            <div className="muted-surface">
              <strong>No direct clause found</strong>
              <p>{finding.search_summary}</p>
            </div>
          ) : (
            finding.vendor_citations.map((citation) => (
              <div key={citation.source_id} className="muted-surface">
                <strong>{citation.source_name}</strong>
                <p>{citation.excerpt}</p>
                <p>
                  Page {citation.page ?? "n/a"} · {citation.section ?? "No section"}
                </p>
              </div>
            ))
          )}
        </article>
      </section>

      <section className="panel stack-md">
        <div>
          <span className="eyebrow">Confidence rationale</span>
          <h2>{(finding.confidence * 100).toFixed(0)}% confidence</h2>
        </div>
        <div className="grid grid-2">
          <div className="muted-surface">Extraction: {(finding.confidence_breakdown.extraction * 100).toFixed(0)}%</div>
          <div className="muted-surface">Retrieval: {(finding.confidence_breakdown.retrieval * 100).toFixed(0)}%</div>
          <div className="muted-surface">Grounding: {(finding.confidence_breakdown.grounding * 100).toFixed(0)}%</div>
          <div className="muted-surface">Rule completion: {(finding.confidence_breakdown.rule_completion * 100).toFixed(0)}%</div>
        </div>
        <div className="muted-surface">
          <strong>Search trace</strong>
          <p>{finding.search_summary}</p>
        </div>
      </section>
    </main>
  );
}
