import Link from "next/link";

import { PackageUploadForm } from "@/components/upload/package-upload-form";
import { PlaybookUploadForm } from "@/components/upload/playbook-upload-form";
import { UploadQueue } from "@/components/upload/upload-queue";
import { getPlaybooks } from "@/lib/api";

const placeholderDocuments = [
  { filename: "master-service-agreement.pdf", documentType: "MSA" },
  { filename: "data-processing-addendum.pdf", documentType: "DPA" },
  { filename: "security-questionnaire.pdf", documentType: "Security" },
  { filename: "insurance-certificate.pdf", documentType: "Insurance" },
  { filename: "company-profile.pdf", documentType: "Profile" },
];

export default async function UploadPage() {
  const playbookResponse = await getPlaybooks().catch(() => ({ items: [] }));

  return (
    <main className="stack-lg">
      <section className="hero">
        <span className="kicker">Real ingestion workflow</span>
        <div className="stack-md">
          <h1>Upload the policy playbook, then analyze a full vendor package against it.</h1>
          <p>
            This workflow now uses real file uploads, SQLite persistence, chunked document parsing,
            local vector retrieval, and heuristic compliance analysis with precise citations.
          </p>
        </div>
        <div className="actions">
          <a className="button" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
            Open API docs
          </a>
          <Link href="/" className="button-secondary">
            Back to dashboard
          </Link>
        </div>
      </section>

      <section className="grid grid-2">
        <PlaybookUploadForm />
        <PackageUploadForm playbooks={playbookResponse.items} />
        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Processing stages</span>
            <h2>Live analysis pipeline</h2>
          </div>
          <div className="stack-sm">
            <div className="muted-surface">1. Playbook persisted and requirementized</div>
            <div className="muted-surface">2. Vendor documents parsed into page-aware chunks</div>
            <div className="muted-surface">3. Chunks indexed into local Chroma collections</div>
            <div className="muted-surface">4. Requirements evaluated across the entire package</div>
            <div className="muted-surface">5. Findings, conflicts, and citations persisted in SQLite</div>
            <div className="muted-surface">6. Review report generated and exportable</div>
          </div>
        </div>
        <UploadQueue items={placeholderDocuments} />
      </section>

      <section className="panel stack-md">
        <div>
          <span className="eyebrow">Playbook inventory</span>
          <h2>{playbookResponse.items.length} playbook version{playbookResponse.items.length === 1 ? "" : "s"} ready</h2>
        </div>
        {playbookResponse.items.length === 0 ? (
          <p>Upload a playbook first. Package analysis is blocked until at least one playbook version exists.</p>
        ) : (
          playbookResponse.items.map((playbook) => (
            <div key={playbook.version_id} className="muted-surface">
              <strong>{playbook.name}</strong>
              <p>
                {playbook.effective_date} · {playbook.requirement_count} extracted requirements · {playbook.status}
              </p>
            </div>
          ))
        )}
      </section>
    </main>
  );
}
