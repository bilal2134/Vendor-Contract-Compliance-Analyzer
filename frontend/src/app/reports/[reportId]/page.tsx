import Link from "next/link";
import { notFound } from "next/navigation";

import { FindingCard } from "@/components/report/finding-card";
import { SummaryMetric } from "@/components/report/summary-metric";
import { API_BASE_URL, getReport } from "@/lib/api";

export default async function ReportPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  const report = await getReport(reportId).catch(() => null);

  if (!report) {
    notFound();
  }

  const totalFindings = Math.max(1, report.findings.length);
  const compliantScore = Math.round((report.summary.compliant / totalFindings) * 100);
  const riskFindings = report.findings.filter((finding) => finding.severity === "critical" || finding.severity === "high");
  const groupedFindings = Object.entries(
    report.findings.reduce<Record<string, typeof report.findings>>((groups, finding) => {
      groups[finding.category] = groups[finding.category] ?? [];
      groups[finding.category].push(finding);
      return groups;
    }, {}),
  );

  return (
    <main className="report-shell">
      <section className="hero hero-report">
        <div className="report-header">
          <div className="stack-sm">
            <span className="kicker">Compliance presentation brief</span>
            <h1>{report.vendor_name}</h1>
            <p>
              Assessed against playbook version {report.playbook_version_id}. This report synthesizes
              evidence across the full vendor package and highlights gaps, conflicts, and areas ready
              for negotiation.
            </p>
          </div>
          <div className="actions">
            <a href={`${API_BASE_URL}/reports/${reportId}/export?format=json`} className="button-secondary" target="_blank" rel="noreferrer">
              Export JSON
            </a>
            <a href={`${API_BASE_URL}/reports/${reportId}/export?format=csv`} className="button-secondary" target="_blank" rel="noreferrer">
              Export CSV
            </a>
            <Link href={`/reports/${reportId}/conflicts`} className="button-secondary">
              Review conflicts
            </Link>
            <Link href="/upload" className="button">
              Add another package
            </Link>
          </div>
        </div>
        <div className="report-banner-grid">
          <div className="spotlight-card">
            <span className="eyebrow">Overall alignment</span>
            <strong>{compliantScore}%</strong>
            <p>Share of current findings landing fully compliant.</p>
          </div>
          <div className="spotlight-card spotlight-critical">
            <span className="eyebrow">High-risk items</span>
            <strong>{riskFindings.length}</strong>
            <p>Critical or high-severity findings that need negotiation attention.</p>
          </div>
          <div className="spotlight-card">
            <span className="eyebrow">Cross-document conflicts</span>
            <strong>{report.conflicts.length}</strong>
            <p>Contradictions discovered across submitted vendor materials.</p>
          </div>
        </div>
      </section>

      <section className="grid grid-3">
        <SummaryMetric label="Compliant" value={report.summary.compliant} tone="accent" helper="Ready to accept" />
        <SummaryMetric label="Partial" value={report.summary.partial} helper="Needs clarification" />
        <SummaryMetric label="Missing or conflict" value={report.summary.missing + report.summary.conflicts} tone="critical" helper="Escalate quickly" />
      </section>

      <section className="grid grid-2 report-overview-grid">
        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Executive readout</span>
            <h2>Where this vendor package stands</h2>
          </div>
          <p>
            The package has {report.findings.length} evaluated findings across {groupedFindings.length} policy domains.
            The reviewer should prioritize {riskFindings.length} high-risk items and {report.conflicts.length} explicit conflicts.
          </p>
          <div className="stack-sm">
            {riskFindings.slice(0, 3).map((finding) => (
              <div key={finding.finding_id} className="muted-surface">
                <strong>{finding.title}</strong>
                <p>{finding.summary}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Coverage map</span>
            <h2>Findings by policy domain</h2>
          </div>
          <div className="stack-sm">
            {groupedFindings.map(([category, findings]) => (
              <div key={category} className="row between muted-surface">
                <strong>{category}</strong>
                <span className="badge muted">{findings.length} findings</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="stack-lg">
        <div>
          <span className="eyebrow">Findings by domain</span>
          <h2>Negotiation-ready evidence groups</h2>
        </div>
        {groupedFindings.map(([category, findings]) => (
          <section key={category} className="stack-md grouped-section">
            <div className="row between grouped-header">
              <div>
                <span className="eyebrow">Policy domain</span>
                <h3>{category}</h3>
              </div>
              <span className="badge">{findings.length} findings</span>
            </div>
            {findings.map((finding) => (
              <div key={finding.finding_id} className="stack-sm">
                <FindingCard finding={finding} />
                <div className="actions">
                  <Link href={`/reports/${reportId}/findings/${finding.finding_id}`} className="button-secondary">
                    Open finding detail
                  </Link>
                </div>
              </div>
            ))}
          </section>
        ))}
      </section>
    </main>
  );
}
