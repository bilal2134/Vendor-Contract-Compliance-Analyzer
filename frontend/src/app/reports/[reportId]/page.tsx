import Link from "next/link";
import { notFound } from "next/navigation";

import { FindingCard } from "@/components/report/finding-card";
import { SummaryMetric } from "@/components/report/summary-metric";
import { getReport } from "@/lib/api";

export default async function ReportPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  const report = await getReport(reportId).catch(() => null);

  if (!report) {
    notFound();
  }

  return (
    <main className="report-shell">
      <section className="hero">
        <div className="report-header">
          <div className="stack-sm">
            <span className="kicker">Compliance report</span>
            <h1>{report.vendor_name}</h1>
            <p>
              Playbook version {report.playbook_version_id} with {report.findings.length} findings and {" "}
              {report.conflicts.length} conflict objects ready for reviewer inspection.
            </p>
          </div>
          <div className="actions">
            <Link href={`/reports/${reportId}/conflicts`} className="button-secondary">
              Review conflicts
            </Link>
            <Link href="/upload" className="button">
              Add another package
            </Link>
          </div>
        </div>
      </section>

      <section className="grid grid-3">
        <SummaryMetric label="Compliant" value={report.summary.compliant} />
        <SummaryMetric label="Partial" value={report.summary.partial} />
        <SummaryMetric label="Missing or conflict" value={report.summary.missing + report.summary.conflicts} />
      </section>

      <section className="stack-md">
        <div>
          <span className="eyebrow">Findings</span>
          <h2>Reviewer-ready findings grouped in a single stream</h2>
        </div>
        {report.findings.map((finding) => (
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
    </main>
  );
}
