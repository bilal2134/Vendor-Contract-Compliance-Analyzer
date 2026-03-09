# Vendor Contract Compliance Analyzer

Local-first procurement compliance analysis platform for reviewing vendor submission packages against a large internal playbook.

## What is implemented

- Real playbook upload and version persistence in SQLite
- Real vendor package upload with MSA, DPA, security, insurance, and profile inputs
- Local text extraction for PDF, DOCX, TXT, and Markdown documents
- Page-aware chunking plus requirement extraction from the playbook
- Local Chroma indexing with deterministic embeddings for minimal setup
- Requirement-centric package analysis with citation-rich findings
- Package-level conflict detection for contradictory terms across vendor documents
- Dashboard, upload workspace, report drill-down, and JSON/CSV export
- Optional Gemini summarization for richer finding text when `GEMINI_API_KEY` is set

## Structure

- `backend/`: FastAPI application, workers, schemas, and services.
- `frontend/`: Next.js reviewer interface.
- `docs/`: Architecture and evaluation notes.

## Milestones

1. Foundation: FastAPI, Next.js, local storage, SQLite, Chroma
2. Ingestion: playbook parsing, vendor package parsing, chunking, persistence
3. Analysis: requirement extraction, cross-document retrieval, conflict detection, report generation
4. Review UX: dashboard, upload, report, finding detail, conflict review, export
5. Validation: backend tests, frontend production build, live API smoke tests

## Local setup

### Backend

1. Create and activate the virtual environment if it does not already exist.
2. Install backend dependencies:
   - `& ".venv/Scripts/python.exe" -m pip install -e backend`
3. Optional: copy `.env.example` to `.env` and set `GEMINI_API_KEY` if you want Gemini-based finding summaries.
4. Run the API from the repo root:
   - `& ".venv/Scripts/python.exe" -m uvicorn app.main:app --reload --app-dir backend`

### Frontend

1. Install dependencies:
   - `Set-Location frontend`
   - `npm install`
2. Run the app:
   - `npm run dev`

## How to use it

1. Open `http://127.0.0.1:3000/upload`
2. Upload the procurement playbook first
3. Upload the vendor package files, with the MSA required and the other package documents recommended
4. The app will create a report automatically and route you to the report page
5. Export the report from the report header as JSON or CSV

## How to test it

### Backend tests

- `Set-Location backend`
- `& "../.venv/Scripts/python.exe" -m pytest tests`

### Frontend build

- `Set-Location frontend`
- `npm run build`

### API docs

- `http://127.0.0.1:8000/docs`

## Current limitations

- OCR for scanned image-only PDFs is not included yet
- Embeddings are deterministic local hash embeddings for minimal setup, not semantic foundation-model embeddings
- Gemini is optional and currently used only to improve finding summaries, not to replace the grounded rule engine
