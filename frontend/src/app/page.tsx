import Link from "next/link";

import { FindingCard } from "@/components/report/finding-card";
import { SummaryMetric } from "@/components/report/summary-metric";
import { getDashboard, getReport } from "@/lib/api";

export default async function HomePage() {
  const dashboard = await getDashboard().catch(() => ({ cards: [] }));
  const featuredReport = dashboard.cards[0]?.report_id
    ? await getReport(dashboard.cards[0].report_id).catch(() => null)
    : null;

  return (
    <main className="stack-lg">
      <section className="hero">
        <span className="kicker">Procurement review workspace</span>
        <div className="stack-md">
          <h1>Vendor package analysis with grounded policy citations and explicit uncertainty.</h1>
          <p>
            This first implementation slice wires the intake and reviewer experience together so
            compliance findings, conflicts, and missing evidence can be inspected before the full
            retrieval and reasoning stack lands.
          </p>
        </div>
        <div className="actions">
          <Link href="/upload" className="button">
            Upload vendor package
          </Link>
          {dashboard.cards[0]?.report_id ? (
            <Link href={`/reports/${dashboard.cards[0].report_id}`} className="button-secondary">
              Open latest report
            </Link>
          ) : null}
        </div>
      </section>

      <section className="grid grid-3">
        <SummaryMetric label="Active packages" value={dashboard.cards.length} />
        <SummaryMetric
          label="Critical review items"
          value={dashboard.cards.reduce((sum, card) => sum + card.critical_findings, 0)}
        />
        <SummaryMetric label="Playbook versions" value={1} />
      </section>

      <section className="grid grid-2">
        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Queue snapshot</span>
            <h2>Current review workload</h2>
          </div>
          {dashboard.cards.length === 0 ? (
            <p>No package jobs exist yet. Create one from the upload workspace.</p>
          ) : (
            dashboard.cards.map((card) => (
              <Link key={card.package_id} href={`/reports/${card.report_id}`} className="muted-surface">
                <div className="row between">
                  <strong>{card.vendor_name}</strong>
                  <span className="badge muted">{card.status}</span>
                </div>
                <p>{card.critical_findings} critical or missing review items</p>
              </Link>
            ))
          )}
        </div>

        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Design intent</span>
            <h2>What this baseline proves</h2>
          </div>
          <div className="stack-sm">
            <p>Requirement-centric report structure with explicit statuses and confidence scoring.</p>
            <p>Side-by-side policy and vendor evidence model for drill-down workflows.</p>
            <p>Conflict findings represented as first-class review objects, not buried notes.</p>
          </div>
        </div>
      </section>

      {featuredReport ? (
        <section className="stack-md">
          <div>
            <span className="eyebrow">Featured finding</span>
            <h2>{featuredReport.vendor_name} seeded report preview</h2>
          </div>
          <FindingCard finding={featuredReport.findings[0]} />
        </section>
      ) : null}
    </main>
  );
}
