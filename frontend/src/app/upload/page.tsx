import Link from "next/link";

import { PackageUploadForm } from "@/components/upload/package-upload-form";
import { PlaybookUploadForm } from "@/components/upload/playbook-upload-form";
import { getPlaybooks } from "@/lib/api";

const PIPELINE_STEPS = [
  { icon: "📄", label: "Parse & chunk documents" },
  { icon: "🧠", label: "Gemini 3 072-dim embeddings" },
  { icon: "🔍", label: "Semantic retrieval" },
  { icon: "⚖️", label: "Compliance matching" },
  { icon: "✨", label: "AI summarisation" },
  { icon: "📊", label: "Report generation" },
];

export default async function UploadPage() {
  const playbookResponse = await getPlaybooks().catch(() => ({ items: [] }));

  return (
    <main className="stack-lg">
      {/* Page header */}
      <section className="page-header stack-sm">
        <Link href="/" className="back-link">← Dashboard</Link>
        <div>
          <span className="kicker">New compliance review</span>
          <h1>Upload workspace</h1>
          <p className="form-hint" style={{ maxWidth: 580 }}>
            Upload a policy playbook first, then submit a 5-document vendor package. The analysis
            engine evaluates every requirement and produces a full cited report.
          </p>
        </div>
      </section>

      {/* Wizard step indicator */}
      <div className="wizard-track">
        <div className="wizard-step-item">
          <div className="wizard-step-num active">1</div>
          <span className="wizard-step-title active">Policy Playbook</span>
        </div>
        <div className="wizard-connector" />
        <div className="wizard-step-item">
          <div className="wizard-step-num active">2</div>
          <span className="wizard-step-title active">Vendor Package</span>
        </div>
        <div className="wizard-connector" />
        <div className="wizard-step-item">
          <div className="wizard-step-num">3</div>
          <span className="wizard-step-title">Compliance Report</span>
        </div>
      </div>

      {/* Two-column form grid */}
      <section className="grid grid-2">
        <PlaybookUploadForm />
        <PackageUploadForm playbooks={playbookResponse.items} />
      </section>

      {/* Analysis pipeline visualization */}
      <section className="panel stack-md">
        <div>
          <span className="eyebrow">How it works</span>
          <h2>Analysis pipeline</h2>
          <p className="form-hint">
            Each vendor package runs through 6 automated stages in sequence.
          </p>
        </div>
        <div className="pipeline-grid">
          {PIPELINE_STEPS.map((step, idx) => (
            <div key={step.label} className="pipeline-node">
              <span className="pipeline-icon">{step.icon}</span>
              <span className="kicker" style={{ fontSize: "0.68rem" }}>Stage {idx + 1}</span>
              <span className="pipeline-label">{step.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Loaded playbooks summary */}
      {playbookResponse.items.length > 0 && (
        <section className="panel stack-md">
          <div>
            <span className="eyebrow">Playbook inventory</span>
            <h2>
              {playbookResponse.items.length} playbook version
              {playbookResponse.items.length === 1 ? "" : "s"} ready
            </h2>
          </div>
          <div className="stack-sm">
            {playbookResponse.items.map((pb) => (
              <div key={pb.version_id} className="muted-surface">
                <strong>{pb.name}</strong>
                <p style={{ margin: "4px 0 0", fontSize: "0.85rem" }}>
                  Effective {pb.effective_date} · {pb.requirement_count} requirements · {pb.status}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
