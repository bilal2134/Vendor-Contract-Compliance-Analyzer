"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

const defaultDocuments = [
  { filename: "master-service-agreement.pdf", document_type: "msa" },
  { filename: "data-processing-addendum.pdf", document_type: "dpa" },
  { filename: "security-questionnaire.pdf", document_type: "security" },
  { filename: "insurance-certificate.pdf", document_type: "insurance" },
  { filename: "company-profile.pdf", document_type: "profile" },
];

interface CreatePackageResponse {
  package_id: string;
  job_id: string;
  report_id: string | null;
  status: string;
}

export function PackageUploadForm() {
  const router = useRouter();
  const [vendorName, setVendorName] = useState("Northstar Cloud Systems");
  const [playbookVersionId, setPlaybookVersionId] = useState("active");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await fetch(`${API_BASE_URL}/ingestion/packages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          vendor_name: vendorName,
          playbook_version_id: playbookVersionId,
          documents: defaultDocuments,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const result = (await response.json()) as CreatePackageResponse;
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
        <span className="eyebrow">Create seeded package</span>
        <h2>Kick off the first review job</h2>
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
        <input
          className="field"
          value={playbookVersionId}
          onChange={(event) => setPlaybookVersionId(event.target.value)}
          placeholder="active"
        />
      </label>
      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Creating package..." : "Create package job"}
      </button>
      {errorMessage ? <p>{errorMessage}</p> : null}
    </form>
  );
}
