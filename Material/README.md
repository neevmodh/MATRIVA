# MATRIVA visual atlas

Architecture, request flow, user journeys and real application captures, in one place. The diagrams describe the implemented repository; the screenshots come from a running local frontend and API.

[Project README](../README.md) · [Diagram atlas](#diagram-atlas) · [Application captures](#application-captures) · [Reproduce the material](#reproduce-the-material)

The colorful README graphics are available as an editable [cover SVG](./branding/readme-cover.svg) and [project-highlights SVG](./branding/readme-highlights.svg). Both are self-contained vector assets with accessible titles and explicit dimensions.

![MATRIVA landing page](./screenshots/01-landing.jpg)

## Diagram atlas

Seven diagrams explain the implemented application. SVG preserves sharp text at any zoom, PNG is convenient for slides, and Mermaid provides an editable graph. The six core atlas diagrams use a shared generator; the standalone RAG pipeline is editable directly as SVG or Mermaid and uses the same PNG export tool.

| Diagram | What it explains | Exports |
|---|---|---|
| System architecture | Browser/API boundaries, server modules, persistence and optional providers | [SVG](./diagrams/architecture.svg) · [PNG](./diagrams/architecture.png) · [Mermaid](./diagrams/architecture.mmd) |
| Chat working flow | Input safety, evidence gate, two retrieval engines, composition and final streaming validation | [SVG](./diagrams/working-flow.svg) · [PNG](./diagrams/working-flow.png) · [Mermaid](./diagrams/working-flow.mmd) |
| RAG pipeline | Reviewed knowledge, seven retrieval signals, ranking, sufficiency, extractive answers and the optional external engine | [SVG](./diagrams/rag-pipeline.svg) · [PNG](./diagrams/rag-pipeline.png) · [Mermaid](./diagrams/rag-pipeline.mmd) |
| User flow | Account creation, consent, chat, care tools and privacy controls | [SVG](./diagrams/user-flow.svg) · [PNG](./diagrams/user-flow.png) · [Mermaid](./diagrams/user-flow.mmd) |
| Source-review workflow | Upload, extraction, indexing, human review and retrieval eligibility | [SVG](./diagrams/source-review.svg) · [PNG](./diagrams/source-review.png) · [Mermaid](./diagrams/source-review.mmd) |
| Production deployment | Four Compose services, private networking, volumes and operator-managed ingress | [SVG](./diagrams/deployment.svg) · [PNG](./diagrams/deployment.png) · [Mermaid](./diagrams/deployment.mmd) |
| Privacy flow | Consent, export, profile deletion and account deletion scopes | [SVG](./diagrams/privacy-flow.svg) · [PNG](./diagrams/privacy-flow.png) · [Mermaid](./diagrams/privacy-flow.mmd) |

### System architecture

![Architecture of the modular Next.js and FastAPI application](./diagrams/architecture.svg)

Grounded in [API startup](../backend/app/main.py), [chat orchestration](../backend/app/services/chat.py), [local retrieval](../backend/app/rag/local/), [care services](../backend/app/services/care/) and [production Compose](../docker-compose.prod.yml).

### Chat working flow

![Flowchart of question processing, safety exits, retrieval, evidence checks and delivery](./diagrams/working-flow.svg)

Grounded in [chat orchestration](../backend/app/services/chat.py), the [external pipeline](../backend/app/rag/pipeline.py), the [offline engine](../backend/app/rag/local/engine.py) and [output checks](../backend/app/safety/guardrails/output.py). Safety exits and insufficient-evidence replies are fixed paths. The validated final SSE event may correct earlier deltas.

### RAG pipeline

![MATRIVA RAG pipeline from source review through hybrid retrieval to cited answers, with safety and insufficient-evidence exits](./diagrams/rag-pipeline.svg)

Grounded in [chat orchestration](../backend/app/services/chat.py), [corpus eligibility](../backend/app/rag/local/corpus.py), [local retrieval](../backend/app/rag/local/retriever.py), [extractive composition](../backend/app/rag/local/composer.py) and the [external pipeline](../backend/app/rag/pipeline.py). The default path is offline and extractive. The inset describes the optional Gemini/pgvector and LangChain/Groq path. Read the [RAG overview](../docs/rag.md) and [local engine details](../docs/local-rag.md).

### User flow

![User journey from landing through consent to chat, care and privacy](./diagrams/user-flow.svg)

Grounded in [onboarding](../frontend/app/onboarding/page.tsx), the [chat workspace and shortcut definitions](../frontend/app/chat/page.tsx) and [Settings](../frontend/app/settings/page.tsx). Staff review uses a separate role-gated route.

### Source review

![Document workflow from pending upload to approved retrieval or exclusion](./diagrams/source-review.svg)

Grounded in [admin endpoints](../backend/app/api/admin.py), [knowledge processing](../backend/app/services/knowledge.py) and [corpus eligibility](../backend/app/rag/local/corpus.py). No screenshot fixture is approved. Administrative approval is distinct from clinical review.

### Deployment

![Production topology with operator ingress, Next.js, FastAPI, PostgreSQL and Redis](./diagrams/deployment.svg)

Grounded in [production Compose](../docker-compose.prod.yml), the [backend image](../backend/Dockerfile), the [frontend image](../frontend/Dockerfile) and the [entrypoint](../backend/docker-entrypoint.sh). This is a deployment topology, not a claim that a public deployment exists. Compose supplies internal service ports; public HTTPS ingress remains operator-managed.

### Privacy

![Consent and deletion flow with separate export, profile and account operations](./diagrams/privacy-flow.svg)

Grounded in [privacy endpoints](../backend/app/api/privacy.py), [profile endpoints](../backend/app/api/profile.py) and [care privacy operations](../backend/app/services/care/privacy.py). Withdrawing health consent retains chat history; account deletion has a broader scope. The [privacy guide](../docs/privacy.md) explains the records involved.

## Application captures

**All records are synthetic.** Capture runs use a disposable SQLite database, offline RAG, blank provider keys and disabled tracing. Screens are actual UI output against real API requests, with no network mocks. Only animations and the Next.js development indicator are suppressed for capture.

The [manifest](./capture-manifest.json) records the source revision, timestamp, viewport sizes and browser-error result. The source commit refers to the application snapshot used for the capture, before the documentation commit itself.

| Screen | View |
|---|---|
| 01 · Public landing | [Open JPEG](./screenshots/01-landing.jpg) |
| 02 · Account creation | [Open JPEG](./screenshots/02-signup.jpg) |
| 03 · Profile onboarding and consent | [Open JPEG](./screenshots/03-onboarding.jpg) |
| 04 · Chat workspace | [Open JPEG](./screenshots/04-chat-workspace.jpg) |
| 05 · Weekly plan | [Open JPEG](./screenshots/05-weekly-plan.jpg) |
| 06 · Health readings and trend | [Open JPEG](./screenshots/06-health-readings.jpg) |
| 07 · Meal journal | [Open JPEG](./screenshots/07-meal-journal.jpg) |
| 08 · Food guide | [Open JPEG](./screenshots/08-food-guide.jpg) |
| 09 · Doctor summary | [Open JPEG](./screenshots/09-doctor-summary.jpg) |
| 10 · Emergency safety response | [Open JPEG](./screenshots/10-emergency-response.jpg) |
| 11 · Privacy and safety settings | [Open JPEG](./screenshots/11-privacy-settings.jpg) |
| 12 · Mobile chat workspace | [Open JPEG](./screenshots/12-mobile-workspace.jpg) |
| 13 · Staff source-review queue | [Open JPEG](./screenshots/13-source-review.jpg) |

| Account creation | Consent step |
|---|---|
| ![Blank signup screen](./screenshots/02-signup.jpg) | ![Week-20 onboarding before storage consent](./screenshots/03-onboarding.jpg) |

| Workspace | Weekly plan |
|---|---|
| ![Desktop chat workspace](./screenshots/04-chat-workspace.jpg) | ![Synthetic user's weekly plan](./screenshots/05-weekly-plan.jpg) |

| Readings | Meal journal |
|---|---|
| ![Synthetic haemoglobin readings and trend](./screenshots/06-health-readings.jpg) | ![Parsed synthetic meal and nutrients](./screenshots/07-meal-journal.jpg) |

| Food guide | Doctor summary |
|---|---|
| ![Traditional food material and nutrient guide](./screenshots/08-food-guide.jpg) | ![Summary prepared from synthetic care records](./screenshots/09-doctor-summary.jpg) |

| Emergency path | Privacy settings |
|---|---|
| ![Real fixed response to a scripted emergency input](./screenshots/10-emergency-response.jpg) | ![Consent, safety profile, export and deletion settings](./screenshots/11-privacy-settings.jpg) |

### Mobile workspace

<img src="./screenshots/12-mobile-workspace.jpg" width="390" alt="Responsive chat workspace at 390 by 844 pixels"/>

### Staff review queue

![Admin review queue showing three pending synthetic documents](./screenshots/13-source-review.jpg)

The queue fixtures are explicitly labelled synthetic and uncertain. This capture demonstrates the administrative workflow; it supplies no clinical guidance or approval.

## Reproduce the material

Use an installed backend virtual environment and frontend dependencies from the [local setup](../README.md#run-locally). Install Chromium once:

```bash
cd frontend
npm ci
npx playwright install chromium
cd ..
```

From the repository root:

```bash
# Generate the six SVG diagrams and their Mermaid graph sources
python3 Material/tools/render_diagrams.py

# Export SVGs as 2× PNGs without starting the app
node Material/tools/capture.mjs --diagrams-only

# Run the real local API/UI, capture all screens and write the manifest
python3 Material/tools/capture.py
```

[render_diagrams.py](./tools/render_diagrams.py) uses only the Python standard library. [capture.py](./tools/capture.py) selects loopback ports and starts its own API and frontend processes. [capture.mjs](./tools/capture.mjs) uses the repository's Playwright installation, signs in through the UI, creates synthetic care records through the API and captures the application.

The capture uses environment overrides without modifying existing `.env` files. Its reviewer role exists only in the temporary database. It leaves all uploaded fixtures pending, stops only the two processes it created and removes its temporary database on exit. Source rules remain clinically unreviewed. Date-sensitive plan labels change when captures are regenerated.

## Original supporting PDFs

The two unique PDFs previously stored in lowercase `material/` remain in this capitalized directory. They are preserved source/history documents, separate from the generated atlas:

- [Original presentation](./Presentaion.pdf).
- [Original Garbhini Paricharya supporting document](./understandingofgarbhiniparicharyaanditspracticalapproach-260525114930-5d0a9447%20%281%29.pdf).

The canonical book remains in [knowledge/ayurveda](../knowledge/ayurveda/). See the [repository audit](../docs/repository-audit.md) for the earlier duplicate-file cleanup.
