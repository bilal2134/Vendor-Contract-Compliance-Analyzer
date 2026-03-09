# Architecture Snapshot

## Current implementation slice

This repository currently implements the first end-to-end vertical slice for the Vendor Contract Compliance Analyzer:

- FastAPI API surface for playbook and package job creation
- report retrieval, dashboard retrieval, and reviewer-note endpoints
- shared typed schemas for jobs, citations, findings, conflicts, and reports
- seeded in-memory orchestration layer to prove end-to-end contracts
- Next.js reviewer UI for dashboard, upload, report, finding detail, and conflict review

## Next backend milestones

1. Replace in-memory repository with PostgreSQL-backed persistence.
2. Add real file ingestion and object storage references.
3. Add OCR, parser, and chunk provenance pipeline.
4. Add Chroma-backed retrieval and Gemini-powered requirement evaluation.
5. Enforce citation validation against persisted provenance objects.

## Next frontend milestones

1. Wire upload page to live package creation.
2. Add polling for stage-based job status.
3. Add reviewer notes, overrides, and export flows.
4. Add side-by-side source document viewer with highlighted citations.
