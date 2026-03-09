import Link from "next/link";

import { FindingCard } from "@/components/report/finding-card";
import { SummaryMetric } from "@/components/report/summary-metric";
import { getDashboard, getPlaybooks, getReport } from "@/lib/api";

export default async function HomePage() {
  const dashboard = await getDashboard().catch(() => ({ cards: [] }));
  const playbooks = await getPlaybooks().catch(() => ({ items: [] }));
  const featuredReport = dashboard.cards[0]?.report_id
    ? await getReport(dashboard.cards[0].report_id).catch(() => null)
    : null;

  return (
    <main className="stack-lg">
      <section className="hero">
        <span className="kicker">Procurement review command center</span>
        <div className="stack-md">
          <h1>Turn dense policy playbooks and scattered vendor submissions into a negotiation-ready compliance brief.</h1>
          <p>
            The platform now ingests a real playbook, analyzes multi-document vendor packages, and
            surfaces grounded findings with citations, confidence, conflicts, and exportable outputs.
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
        <SummaryMetric label="Active packages" value={dashboard.cards.length} tone="accent" helper="Persisted in SQLite" />
        <SummaryMetric
          label="Critical review items"
          value={dashboard.cards.reduce((sum, card) => sum + card.critical_findings, 0)}
          tone="critical"
          helper="Missing clauses plus conflicts"
        />
        <SummaryMetric label="Playbook versions" value={playbooks.items.length} helper="Versioned policy baselines" />
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
            <h2>What the live build proves</h2>
          </div>
          <div className="stack-sm">
            <p>Requirement-centric analysis across all uploaded vendor documents, not isolated clause search.</p>
            <p>Grounded report outputs with playbook and vendor citations ready for escalation and negotiation.</p>
            <p>Conflict findings elevated into first-class review objects instead of buried footnotes.</p>
            <p>Local-first storage and retrieval with optional Gemini enrichment for sharper summaries.</p>
          </div>
        </div>
      </section>

      {featuredReport ? (
        <section className="stack-md">
          <div>
            <span className="eyebrow">Featured finding</span>
            <h2>{featuredReport.vendor_name} live report preview</h2>
          </div>
          <FindingCard finding={featuredReport.findings[0]} />
        </section>
      ) : null}
    </main>
  );
}
