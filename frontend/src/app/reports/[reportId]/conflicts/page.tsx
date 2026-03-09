import Link from "next/link";
import { notFound } from "next/navigation";

import { getReport } from "@/lib/api";

export default async function ConflictsPage({ params }: { params: Promise<{ reportId: string }> }) {
  const { reportId } = await params;
  const report = await getReport(reportId).catch(() => null);

  if (!report) {
    notFound();
  }

  return (
    <main className="stack-lg">
      <section className="hero">
        <span className="kicker">Conflict review</span>
        <div className="stack-md">
          <h1>{report.vendor_name} conflict workspace</h1>
          <p>
            Conflicts are elevated into their own review surface so contradictory package evidence is
            never flattened into a single AI answer.
          </p>
        </div>
        <div className="actions">
          <Link href={`/reports/${reportId}`} className="button-secondary">
            Back to report
          </Link>
        </div>
      </section>

      <section className="stack-md">
        {report.conflicts.map((conflict) => (
          <article key={conflict.conflict_id} className="panel stack-md severity-critical">
            <div>
              <span className="eyebrow">{conflict.severity} severity</span>
              <h2>{conflict.title}</h2>
              <p>{conflict.summary}</p>
            </div>
            <div className="grid grid-2">
              <div className="muted-surface">
                <strong>{conflict.left_citation.source_name}</strong>
                <p>{conflict.left_citation.excerpt}</p>
              </div>
              <div className="muted-surface">
                <strong>{conflict.right_citation.source_name}</strong>
                <p>{conflict.right_citation.excerpt}</p>
              </div>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}
