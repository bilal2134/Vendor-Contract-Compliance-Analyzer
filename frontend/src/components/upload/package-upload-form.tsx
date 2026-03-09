"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import type { PlaybookSummary } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

interface CreatePackageResponse {
  package_id: string;
  job_id: string;
  report_id: string | null;
  status: string;
  warnings: string[];
}

interface PackageUploadFormProps {
  playbooks: PlaybookSummary[];
}

export function PackageUploadForm({ playbooks }: PackageUploadFormProps) {
  const router = useRouter();
  const [vendorName, setVendorName] = useState("Northstar Cloud Systems");
  const [playbookVersionId, setPlaybookVersionId] = useState(playbooks[0]?.version_id ?? "");
  const [msaFile, setMsaFile] = useState<File | null>(null);
  const [dpaFile, setDpaFile] = useState<File | null>(null);
  const [securityFile, setSecurityFile] = useState<File | null>(null);
  const [insuranceFile, setInsuranceFile] = useState<File | null>(null);
  const [profileFile, setProfileFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

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
    setWarnings([]);

    try {
      const formData = new FormData();
      formData.append("vendor_name", vendorName);
      formData.append("playbook_version_id", playbookVersionId);
      formData.append("msa", msaFile);
      if (dpaFile) {
        formData.append("dpa", dpaFile);
      }
      if (securityFile) {
        formData.append("security", securityFile);
      }
      if (insuranceFile) {
        formData.append("insurance", insuranceFile);
      }
      if (profileFile) {
        formData.append("profile", profileFile);
      }

      const response = await fetch(`${API_BASE_URL}/ingestion/packages/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const result = (await response.json()) as CreatePackageResponse;
      setWarnings(result.warnings);
      if (result.report_id) {
        router.push(`/reports/${result.report_id}`);
        return;
      }
      router.push("/");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unexpected upload error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="panel stack-md" onSubmit={handleSubmit}>
      <div>
        <span className="eyebrow">Step 2</span>
        <h2>Upload vendor submission package</h2>
      </div>
      <label className="stack-sm">
        <span>Vendor name</span>
        <input
          className="field"
          value={vendorName}
          onChange={(event) => setVendorName(event.target.value)}
          placeholder="Vendor legal name"
        />
      </label>
      <label className="stack-sm">
        <span>Playbook version</span>
        <select className="field" value={playbookVersionId} onChange={(event) => setPlaybookVersionId(event.target.value)}>
          <option value="">Select playbook</option>
          {playbooks.map((playbook) => (
            <option key={playbook.version_id} value={playbook.version_id}>
              {playbook.name} · {playbook.effective_date}
            </option>
          ))}
        </select>
      </label>
      <label className="stack-sm">
        <span>MSA file</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setMsaFile(event.target.files?.[0] ?? null)} />
      </label>
      <label className="stack-sm">
        <span>DPA file</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setDpaFile(event.target.files?.[0] ?? null)} />
      </label>
      <label className="stack-sm">
        <span>Security questionnaire / certifications</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setSecurityFile(event.target.files?.[0] ?? null)} />
      </label>
      <label className="stack-sm">
        <span>Insurance certificate</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setInsuranceFile(event.target.files?.[0] ?? null)} />
      </label>
      <label className="stack-sm">
        <span>Company profile / references</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setProfileFile(event.target.files?.[0] ?? null)} />
      </label>
      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Analyzing package..." : "Analyze vendor package"}
      </button>
      {errorMessage ? <p>{errorMessage}</p> : null}
      {warnings.length > 0 ? <p>{warnings.join(" ")}</p> : null}
    </form>
  );
}
