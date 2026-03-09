# Evaluation Plan

## Current validation status

- Backend tests pass for health plus end-to-end playbook upload, package upload, and report retrieval.
- Frontend production build passes.
- Live API smoke tests have covered health, package creation, report retrieval, and export endpoints.

## Release 1 quality targets

- Citation precision: every stored citation must resolve to an actual source object.
- Requirement recall: benchmark set should show the system can evaluate multi-document requirements, not just single-document keyword hits.
- Conflict accuracy: contradictory values across documents must surface as explicit conflicts.
- Missing vs uncertain calibration: absence claims require adequate search coverage and parse quality.
- Reviewer trust: every finding must show evidence, confidence, and search summary.

## Benchmark categories

1. Multi-page playbook sections with tables.
2. Cross-document requirements spanning insurance, MSA, and DPA.
3. Missing-clause scenarios across all expected documents.
4. Conflicting terms across vendor documents.
5. Citation-grounding validation.

## Immediate validation commands

1. `Set-Location backend; & "../.venv/Scripts/python.exe" -m pytest tests`
2. `Set-Location frontend; npm run build`
3. Start the backend and upload one playbook plus one sample package through the UI.
