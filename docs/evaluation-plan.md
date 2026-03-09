# Evaluation Plan

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

## Immediate validation for current scaffold

1. Backend health endpoint returns successfully.
2. Package creation returns a job id and seeded report can be queried.
3. Frontend pages render against the API contracts without type errors.
