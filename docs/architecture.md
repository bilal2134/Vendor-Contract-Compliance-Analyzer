# Architecture Snapshot

## Runtime architecture

- Backend: FastAPI with synchronous SQLite persistence through SQLAlchemy
- Frontend: Next.js App Router with server-rendered report views and client-side upload forms
- Persistence: SQLite for playbooks, packages, documents, chunks, requirements, jobs, reports, and reviewer notes
- Retrieval: local Chroma collections backed by deterministic hashed embeddings for zero-key setup
- Storage: filesystem-backed uploaded source documents under `storage/`
- AI enrichment: optional Gemini summarization gated by `GEMINI_API_KEY`

## Processing pipeline

1. Playbook upload creates a version record, stores the file, extracts text, chunks pages, and derives requirements.
2. Vendor package upload stores each document, extracts text, chunks pages, indexes package chunks, and runs requirement-centric analysis.
3. Analysis compares each playbook requirement against retrieved package evidence, emits compliant/partial/non-compliant/missing/conflict findings, and stores precise citations.
4. A package-level conflict detector independently looks for contradictory notice-period language so cross-document contradictions are surfaced even when the playbook does not phrase them perfectly.
5. Reports are persisted and can be queried or exported as JSON or CSV.

## Design choices

- SQLite was chosen over PostgreSQL for the current build because the priority is minimal setup while staying product-shaped.
- Chroma is local and persistent, but embeddings are deterministic and local rather than LLM-derived so the system can run without API keys.
- Gemini is optional because the core system must remain usable without external credentials.

## Next quality upgrades

1. OCR pipeline for scanned PDFs.
2. Stronger semantic embeddings.
3. Richer normalized fact extraction for tables and numeric obligations.
4. Background job execution instead of request-time analysis.
5. Reviewer note display and source-document highlighting in the UI.
