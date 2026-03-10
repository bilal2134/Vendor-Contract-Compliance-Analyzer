"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { PlaybookSummary } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

const ANALYSIS_STEPS = [
  {
    label: "Uploading vendor documents",
    detail: "Transmitting 5 files to the compliance server",
  },
  {
    label: "Extracting & chunking text",
    detail: "PDF / DOCX / TXT parsed with page-aware chunking",
  },
  {
    label: "Indexing with Gemini embeddings",
    detail: "Building 3 072-dim semantic vectors into Chroma",
  },
  {
    label: "Running compliance analysis",
    detail: "Evaluating each requirement via Gemini — this is the longest step (30–60 s)",
  },
  {
    label: "Generating AI summaries",
    detail: "Enriching findings with Gemini Flash",
  },
  {
    label: "Building compliance report",
    detail: "Persisting findings, citations & conflicts to SQLite",
  },
];

// Steps 0-3 auto-advance on a timer; steps 4-5 fire after the API returns.
// Step 3 ("Running compliance analysis") is the real bottleneck — it makes
// one Gemini embed_query call per playbook requirement, so it can take 30-60 s.
// We keep the spinner on step 3 deliberately until the API resolves.
const AUTO_ADVANCE_MS = [0, 950, 2300, 5000];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface FilePickerProps {
  label: string;
  badge: string;
  required?: boolean;
  file: File | null;
  onChange: (file: File | null) => void;
}

function FilePicker({ label, badge, required, file, onChange }: FilePickerProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <div className="file-picker-wrap">
      <div className="file-picker-meta">
        <span className={`doc-type-badge doc-type-${badge.toLowerCase()}`}>{badge}</span>
        <span className="file-picker-label-text">{label}</span>
        {required && <span className="required-star">required</span>}
      </div>
      {file ? (
        <div className="file-selected-card">
          <span className="file-icon-glyph">&#x1F4C4;</span>
          <div className="file-info">
            <span className="file-info-name">{file.name}</span>
            <span className="file-info-size">{formatFileSize(file.size)}</span>
          </div>
          <button
            type="button"
            className="file-clear-btn"
            onClick={() => {
              onChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            &times;
          </button>
        </div>
      ) : (
        <div className="file-drop-zone" onClick={() => inputRef.current?.click()}>
          <span className="file-drop-hint">Click to select file</span>
          <span className="file-drop-fmts">PDF &middot; DOCX &middot; TXT &middot; MD</span>
        </div>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        className="sr-only-input"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}

interface PackageUploadFormProps {
  playbooks: PlaybookSummary[];
}

export function PackageUploadForm({ playbooks }: PackageUploadFormProps) {
  const router = useRouter();
  const [vendorName, setVendorName] = useState("NovaTech Solutions");
  const [playbookVersionId, setPlaybookVersionId] = useState(playbooks[0]?.version_id ?? "");
  const [msaFile, setMsaFile] = useState<File | null>(null);
  const [dpaFile, setDpaFile] = useState<File | null>(null);
  const [securityFile, setSecurityFile] = useState<File | null>(null);
  const [insuranceFile, setInsuranceFile] = useState<File | null>(null);
  const [profileFile, setProfileFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const apiResolvedRef = useRef(false);
  const stepRef = useRef(0);

  useEffect(() => {
    if (!isSubmitting) {
      setCurrentStep(-1);
      return;
    }
    apiResolvedRef.current = false;
    setCurrentStep(0);
    stepRef.current = 0;

    const timers: ReturnType<typeof setTimeout>[] = [];
    AUTO_ADVANCE_MS.forEach((ms, idx) => {
      if (idx === 0) return;
      timers.push(
        setTimeout(() => {
          if (!apiResolvedRef.current) {
            setCurrentStep(idx);
            stepRef.current = idx;
          }
        }, ms),
      );
    });

    return () => timers.forEach(clearTimeout);
  }, [isSubmitting]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!playbookVersionId) {
      setErrorMessage("Upload a playbook before creating a vendor package.");
      return;
    }
    if (!msaFile) {
      setErrorMessage("The MSA file is required.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const formData = new FormData();
      formData.append("vendor_name", vendorName);
      formData.append("playbook_version_id", playbookVersionId);
      formData.append("msa", msaFile);
      if (dpaFile) formData.append("dpa", dpaFile);
      if (securityFile) formData.append("security", securityFile);
      if (insuranceFile) formData.append("insurance", insuranceFile);
      if (profileFile) formData.append("profile", profileFile);

      const response = await fetch(`${API_BASE_URL}/ingestion/packages/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const result = (await response.json()) as {
        package_id: string;
        report_id: string | null;
      };

      apiResolvedRef.current = true;
      for (const s of [4, 5]) {
        if (s > stepRef.current) {
          setCurrentStep(s);
          stepRef.current = s;
          await new Promise((r) => setTimeout(r, 380));
        }
      }
      await new Promise((r) => setTimeout(r, 550));

      router.push(result.report_id ? `/reports/${result.report_id}` : "/");
    } catch (error) {
      setIsSubmitting(false);
      setErrorMessage(error instanceof Error ? error.message : "Unexpected upload error.");
    }
  }

  if (isSubmitting) {
    return (
      <div className="panel analysis-panel">
        <div className="analysis-header">
          <span className="eyebrow">Live pipeline</span>
          <h2>Analyzing vendor package</h2>
          <p className="form-hint">
            This typically takes 15 - 45 seconds. Please keep this tab open.
          </p>
        </div>

        <div className="analysis-steps">
          {ANALYSIS_STEPS.map((step, idx) => {
            const state =
              idx < currentStep ? "done" : idx === currentStep ? "active" : "pending";
            return (
              <div key={step.label} className={`analysis-step analysis-step-${state}`}>
                <div className="step-icon-wrap">
                  {state === "done" && <div className="step-glyph-done">&#10003;</div>}
                  {state === "active" && <span className="step-ring" />}
                  {state === "pending" && <span className="step-glyph-pending" />}
                </div>
                <div className="step-text">
                  <span className="step-label">{step.label}</span>
                  <span className="step-detail">{step.detail}</span>
                </div>
              </div>
            );
          })}
        </div>

        <div className="analysis-vendor-tag">
          Vendor: <strong>{vendorName}</strong>
        </div>
      </div>
    );
  }

  return (
    <form className="panel stack-md" onSubmit={handleSubmit}>
      <div>
        <span className="eyebrow">Step 2</span>
        <h2>Vendor submission package</h2>
        <p className="form-hint">
          Select the 5 vendor documents and run the compliance engine against the uploaded playbook.
        </p>
      </div>

      <label className="stack-xs">
        <span className="form-label">Vendor name</span>
        <input
          className="field"
          value={vendorName}
          onChange={(e) => setVendorName(e.target.value)}
          placeholder="Vendor legal name"
        />
      </label>

      <label className="stack-xs">
        <span className="form-label">Playbook to assess against</span>
        <select
          className="field"
          value={playbookVersionId}
          onChange={(e) => setPlaybookVersionId(e.target.value)}
        >
          <option value="">Select playbook...</option>
          {playbooks.map((pb) => (
            <option key={pb.version_id} value={pb.version_id}>
              {pb.name} - {pb.effective_date}
            </option>
          ))}
        </select>
      </label>

      <div className="file-group">
        <FilePicker
          label="Master Service Agreement"
          badge="MSA"
          required
          file={msaFile}
          onChange={setMsaFile}
        />
        <FilePicker
          label="Data Processing Agreement"
          badge="DPA"
          file={dpaFile}
          onChange={setDpaFile}
        />
        <FilePicker
          label="Security Questionnaire / Certifications"
          badge="SEC"
          file={securityFile}
          onChange={setSecurityFile}
        />
        <FilePicker
          label="Insurance Certificate"
          badge="INS"
          file={insuranceFile}
          onChange={setInsuranceFile}
        />
        <FilePicker
          label="Company Profile / References"
          badge="PRO"
          file={profileFile}
          onChange={setProfileFile}
        />
      </div>

      {errorMessage && <p className="form-error">{errorMessage}</p>}

      <button className="button" type="submit">
        Run compliance analysis
      </button>
    </form>
  );
}