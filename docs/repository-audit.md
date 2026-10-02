# Repository audit — October 2, 2026

The audit inventoried all 414 tracked files: 384 UTF-8 text files and 30 binary assets. It checked hashes and sizes for every file, parsed all 198 Python files plus JSON/YAML configuration and data, resolved internal Python and frontend imports, traced frontend modules from routes/tests/configuration, checked local Markdown links, and reviewed build, deployment, evaluation and GitHub configuration.

No Python/JSON/YAML parsing errors, unresolved internal imports or broken local Markdown links were found. Runtime dependencies and test behavior are verified separately by the repository's test suites and CI.

## Removed files

| Files | Reason |
|---|---|
| `material/992074360-Prasuti-Tantra-by-Dr-premvati-Tiwari.pdf` | Byte-for-byte duplicate of the canonical book in `knowledge/ayurveda/`. Both had SHA-256 `c7fe2263fa1380e280131e2d8925de1430c65cb3137fad54390b8236d66d7c86`. |
| Five `Images/Pasted 2026-09-25 … .heic` files | Unreferenced pasted image artifacts, outside the frontend's public assets and documented screenshots. |
| `frontend/.eslintrc.json` | Superseded by `frontend/eslint.config.mjs`, the active ESLint flat configuration. |
| `frontend/components/pregnancy-visualization.tsx`, `frontend/components/ui/textarea.tsx` | No imports or references from the application, tests or documentation; neither is reachable from the frontend's entry points. |
| `backend/app/personalization/__init__.py`, `backend/app/recommendation/__init__.py` | Empty, unimported scaffold packages. The working implementations are in `app/services/personalization.py` and `app/services/recommendation.py`. |
| `database/seed/.gitkeep`, `frontend/components/ui/.gitkeep` | These directories contain real versioned files and need no placeholder. |
| Four `evaluation/reports/*_eval_report.json` files | Generated snapshots already covered by `.gitignore`. Evaluation runners write fresh outputs; the admin API creates its own run-specific reports. Regeneration commands and mode limitations are documented in the [reports README](../evaluation/reports/README.md). |

Total removed: 17 files, 17,400,443 bytes (about 17.4 MB) from the current tree.

## Supporting cleanup

- Ignore SQLite journal/WAL/shared-memory sidecars and Ruff's cache.
- Point contributor clone instructions and the issue template's security-policy link to `neevmodh/MATRIVA`.
- Route frontend code ownership to the repository owner. GitHub reported the previous owner, `@Rajodedra`, as unknown or lacking write access; no access grants are needed for this correction.
- Update current backend and frontend test counts to 540 and 12, respectively.

## Files retained after reference checks

The canonical book PDF, OCR text, book index, curated datasets, migrations, tests and build/configuration files are required inputs or tooling. The original master prompt and historical sprint/submission documents explain requirements and project history; the submission still embeds the original screenshots. The two unique PDFs in `material/` are original supporting documents, not duplicates. Their lack of runtime imports alone is not a reason to discard the source material.

## Follow-up findings

- Resolved: `main` requires pull requests and all seven CI jobs, including Python 3.14 and the production smoke check. Admin enforcement, conversation resolution and force-push/deletion prevention are enabled.
- Resolved: frontend public images are included in the runtime image and checked against the built container. Redis authentication/readiness, writable reports, OCR availability and provider pin consistency are covered by the production smoke runner.
- Resolved for the existing benchmark: the legacy offline hallucination harness now scores 11/11 after adding query coverage to its grounding gate, and CI asserts all cases abstain before generation. Vector grounding uses unboosted cosine scores. Lexical heuristics and a small benchmark still do not prove clinical answer quality; independent datasets and human review remain necessary.

## Reliability validation

The follow-up fixes add shared Redis quotas across API routes, CORS headers on limit/outage responses, 503 readiness for failed dependencies, bounded route labels in metrics and trusted-proxy defaults. Patched FastAPI/Starlette, PyJWT, multipart, Requests and pytest pins clear the installed-package vulnerability audit. Current regression totals are 566 backend, 43 ingestion, 36 evaluation and 12 mocked browser tests, plus one production browser integration through the actual Docker frontend/API. See [testing](./testing.md) and [deployment](./deployment.md) for repeatable commands and their limits.

Test results and GitHub check links are recorded in the cleanup pull request.
