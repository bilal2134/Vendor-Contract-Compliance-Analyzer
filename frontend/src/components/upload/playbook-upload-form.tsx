"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export function PlaybookUploadForm() {
  const router = useRouter();
  const [name, setName] = useState("Enterprise Procurement Playbook");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("Primary procurement policy baseline");
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage("Select a playbook file before uploading.");
      return;
    }
    setIsSubmitting(true);
    setMessage(null);
    try {
      const formData = new FormData();
      formData.append("name", name);
      formData.append("effective_date", effectiveDate);
      formData.append("description", description);
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/ingestion/playbooks/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const result = (await response.json()) as { version_id: string; requirement_count: number };
      setMessage(`Playbook uploaded as ${result.version_id} with ${result.requirement_count} extracted requirements.`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unexpected playbook upload error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="panel stack-md" onSubmit={handleSubmit}>
      <div>
        <span className="eyebrow">Step 1</span>
        <h2>Upload procurement playbook</h2>
      </div>
      <label className="stack-sm">
        <span>Playbook name</span>
        <input className="field" value={name} onChange={(event) => setName(event.target.value)} />
      </label>
      <label className="stack-sm">
        <span>Effective date</span>
        <input className="field" type="date" value={effectiveDate} onChange={(event) => setEffectiveDate(event.target.value)} />
      </label>
      <label className="stack-sm">
        <span>Description</span>
        <textarea className="field field-area" value={description} onChange={(event) => setDescription(event.target.value)} />
      </label>
      <label className="stack-sm">
        <span>Playbook file</span>
        <input className="field file-field" type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </label>
      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Uploading playbook..." : "Upload playbook"}
      </button>
      {message ? <p>{message}</p> : null}
    </form>
  );
}
