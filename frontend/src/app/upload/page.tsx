import Link from "next/link";

import { PackageUploadForm } from "@/components/upload/package-upload-form";
import { UploadQueue } from "@/components/upload/upload-queue";

const placeholderDocuments = [
  { filename: "master-service-agreement.pdf", documentType: "MSA" },
  { filename: "data-processing-addendum.pdf", documentType: "DPA" },
  { filename: "security-questionnaire.pdf", documentType: "Security" },
  { filename: "insurance-certificate.pdf", documentType: "Insurance" },
  { filename: "company-profile.pdf", documentType: "Profile" },
];

export default function UploadPage() {
  return (
    <main className="stack-lg">
      <section className="hero">
        <span className="kicker">Milestone B</span>
        <div className="stack-md">
          <h1>Seed a vendor package with explicit document typing and job stages.</h1>
          <p>
            The upload API is live in the backend. This page is the first reviewer-facing surface for
            package composition, document taxonomy, and processing-state design.
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
        <PackageUploadForm />
        <div className="panel stack-md">
          <div>
            <span className="eyebrow">Processing stages</span>
            <h2>Current orchestration contract</h2>
          </div>
          <div className="stack-sm">
            <div className="muted-surface">1. Queued</div>
            <div className="muted-surface">2. Parsing</div>
            <div className="muted-surface">3. Extracting</div>
            <div className="muted-surface">4. Indexing</div>
            <div className="muted-surface">5. Analyzing</div>
            <div className="muted-surface">6. Validating</div>
            <div className="muted-surface">7. Complete</div>
          </div>
        </div>
        <UploadQueue items={placeholderDocuments} />
      </section>

      <section className="panel stack-md">
        <div>
          <span className="eyebrow">Next implementation step</span>
          <h2>Wire this page to the package creation endpoint</h2>
        </div>
        <p>
          The backend accepts `vendor_name`, `playbook_version_id`, and typed document metadata. The
          next slice is form submission plus live job polling, followed by real file upload and
          parser status.
        </p>
      </section>
    </main>
  );
}
