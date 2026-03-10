"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function PlaybookUploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("Enterprise Procurement Playbook");
  const [effectiveDate, setEffectiveDate] = useState(new Date().toISOString().slice(0, 10));
  const [description, setDescription] = useState("Primary procurement policy baseline");
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<{ version_id: string; requirement_count: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("Select a playbook file before uploading.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
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
        const errBody = await response.json().catch(() => null);
        const detail = errBody?.detail ?? `Request failed with status ${response.status}`;
        const prefix = response.status === 409 ? "Duplicate playbook: " : "";
        throw new Error(`${prefix}${detail}`);
      }
      const data = (await response.json()) as { version_id: string; requirement_count: number };
      setResult(data);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected playbook upload error.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (result) {
    return (
      <div className="panel stack-md">
        <div className="success-check">&#10003;</div>
        <div>
          <span className="eyebrow">Step 1 complete</span>
          <h2>Playbook indexed</h2>
        </div>
        <div className="req-count-card">
          <span className="req-count-num">{result.requirement_count}</span>
          <span className="req-count-label">
            requirements extracted and ready for compliance matching
          </span>
        </div>
        <p className="form-hint">
          Proceed to Step 2 to upload a vendor package and run the analysis engine.
        </p>
        <button
          className="button-secondary"
          type="button"
          onClick={() => {
            setResult(null);
            setFile(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
        >
          Upload another playbook
        </button>
      </div>
    );
  }

  return (
    <form className="panel stack-md" onSubmit={handleSubmit}>
      <div>
        <span className="eyebrow">Step 1</span>
        <h2>Upload procurement playbook</h2>
        <p className="form-hint">
          The playbook defines policy requirements that all vendor packages are evaluated against.
        </p>
      </div>

      <label className="stack-xs">
        <span className="form-label">Playbook name</span>
        <input
          className="field"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </label>

      <label className="stack-xs">
        <span className="form-label">Effective date</span>
        <input
          className="field"
          type="date"
          value={effectiveDate}
          onChange={(e) => setEffectiveDate(e.target.value)}
        />
      </label>

      <label className="stack-xs">
        <span className="form-label">Description</span>
        <textarea
          className="field field-area"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      <div className="stack-xs">
        <span className="form-label">Playbook file</span>
        {file ? (
          <div className="file-selected-card">
            <span className="file-icon-glyph">&#x1F4CB;</span>
            <div className="file-info">
              <span className="file-info-name">{file.name}</span>
              <span className="file-info-size">{formatFileSize(file.size)}</span>
            </div>
            <button
              type="button"
              className="file-clear-btn"
              onClick={() => {
                setFile(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
            >
              &times;
            </button>
          </div>
        ) : (
          <div className="file-drop-zone" onClick={() => inputRef.current?.click()}>
            <span className="file-drop-hint">Click to select playbook</span>
            <span className="file-drop-fmts">PDF &middot; DOCX &middot; TXT &middot; MD</span>
          </div>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          className="sr-only-input"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>

      {error && <p className="form-error">{error}</p>}

      <button className="button" type="submit" disabled={isSubmitting}>
        {isSubmitting ? (
          <>
            <span className="btn-spinner" />
            Uploading...
          </>
        ) : (
          "Upload playbook"
        )}
      </button>
    </form>
  );
}