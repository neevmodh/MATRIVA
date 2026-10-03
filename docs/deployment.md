# Deployment

## What runs

| Service | Image | Host port | Notes |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | `POSTGRES_PORT` (5432) | PostgreSQL with pgvector. Health check: `pg_isready` |
| `redis` | `redis:7-alpine` | `REDIS_PORT` (6379) | Rate limiting. The production file requires a password and persists to disk |
| `backend` | built from `backend/Dockerfile` (Python 3.11-slim, non-root user) | `BACKEND_PORT` (8000) | Runs `alembic upgrade head`, then Uvicorn. Health check: `GET /health` every 30 s |
| `frontend` | built from `frontend/Dockerfile` (Next.js standalone) | `FRONTEND_PORT` (3000) | `NEXT_PUBLIC_API_URL` is baked in at build time |

Two switches in the backend entrypoint:

| Variable | Default | What it does |
|---|---|---|
| `RUN_MIGRATIONS` | `true` | Run `alembic upgrade head` at start. Set `false` on all but one replica, or run migrations as a release step |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Which proxies Uvicorn trusts for `X-Forwarded-*`. **Set it to your proxy's address in production**; forwarded client addresses affect rate limits |

`docker-compose.prod.yml` differs from the development file: it sets `ENVIRONMENT=production`, `DEBUG=false`, `DEMO_MODE=false` and `AUTO_CREATE_TABLES=false`, **refuses to start unless** `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `REDIS_PASSWORD`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` are set, keeps service ports internal (configure public HTTPS ingress separately), and installs the optional provider packages by default (`INSTALL_OPTIONAL=true`). The host-port values above describe the development Compose file. See the [production topology](../Material/diagrams/deployment.svg).

## Local Docker stack

1. Copy `.env.example` to `.env` and set a unique `JWT_SECRET`.
2. Set `POSTGRES_PASSWORD` and update `DATABASE_URL` if needed.
3. Start the stack:

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before starting Uvicorn. The Compose file
waits for PostgreSQL and Redis health checks. `AUTO_CREATE_TABLES` is disabled in Compose;
migrations are the schema authority.

For a local API-only run:

```bash
cd backend
python -m pip install -r requirements.txt
alembic upgrade head
python ../database/seed/seed.py  # optional; set DEMO_PASSWORD first (database/seed/README.md)
uvicorn app.main:app --reload
```

## Retrieval engine and optional tools

- The default `RAG_ENGINE=local` needs no provider keys. Set `RAG_ENGINE=external` plus
  `LLM_API_KEY` / `EMBEDDING_API_KEY` to use Groq and Gemini.
- Photo import of lab reports needs `tesseract` on a local backend host (`apt install tesseract-ocr`); the Docker image includes it.
- Load the real knowledge with `python scripts/ingest_real_knowledge.py` and
  `python scripts/build_book_index.py`, then approve documents in *Admin → Documents*.
- The frontend ships its own Docker image; see [`frontend/README.md`](../frontend/README.md).

## What the image does not contain

The backend image holds `app/`, `alembic/` and the entrypoint. It does **not** contain:

- **`knowledge/`, `ingestion/` and `backend/scripts/`.** The scripts that load the book and the guidance, and the book itself, are not in the container. Load the knowledge from a checkout of the repository with `DATABASE_URL` pointing at the database:

  ```bash
  cd backend
  DATABASE_URL=postgresql+psycopg://... python scripts/ingest_real_knowledge.py
  DATABASE_URL=... python scripts/build_book_index.py
  ```

  Everything loads as **pending**. Sign in as an admin, open Admin, Documents, and approve what a reviewer has cleared. Until then the chat honestly says it has no reviewed source. The guard rails, care rules, food guide, ontology and the book's structure (`app/data/`) *are* in the image, so they work without this step.
The backend runs as a non-root user and writes its local database and reports under `/app/runtime`. Both Compose files persist that directory in `backend_runtime`. The frontend runtime includes `public/` and listens on `0.0.0.0`, so illustrations and network access work in the deployed image. Its environment contains the public API URL only; backend credentials are not shared with the frontend container.

## Disposable production validation

```bash
cd frontend && npm ci && npx playwright install chromium
cd .. && python scripts/docker_smoke.py --browser
```

This builds the production images, starts fresh PostgreSQL/pgvector and password-protected Redis, upgrades and re-runs migrations, and checks readiness, public images, authentication, consent, care plans, emergency routing, document approval, report writes, shared quotas, export and account deletion. The browser uses the actual frontend and API, including CORS and streaming. Synthetic credentials are passed through the Compose process environment; an empty temporary environment file prevents loading your `.env` without storing passwords on disk. Only its uniquely named containers and volumes are removed afterward. Omit `--browser` for HTTP-only checks.

## Production checklist

- Use `docker-compose.prod.yml` or an orchestrator with secret management.
- Set a unique `JWT_SECRET` of at least 32 characters.
- Set `ENVIRONMENT=production`, `DEBUG=false`, and `DEMO_MODE=false`.
- Use a managed PostgreSQL/pgvector instance, encrypted backups, and a private Redis network.
- Run migrations as a controlled release step, not concurrently from every replica.
- Put the API behind TLS and a reverse proxy/load balancer.
- Configure exact `CORS_ORIGINS`; do not use `*` with credentials.
- Provider packages use one set of main requirements pins. `INSTALL_OPTIONAL` remains accepted for compatibility; the build runs `pip check` in either mode.
- Keep provider keys in a secret manager; never expose them through frontend environment variables.
- Restrict `/admin`, `/evaluation`, and `/internal/metrics` at the network and authorization layers.
- Run backend tests, Ruff, secret scan, and safety evaluation before release.
- Establish a clinical source-review owner and guideline renewal schedule.

## Release steps, in order

1. Run the tests and the checks in [`testing.md`](./testing.md); do not deploy on red.
2. Re-check the facts that go stale: helpline numbers, the MTP Act weeks and the PCPNDT wording in [`data-sources.md`](./data-sources.md#5-helplines-and-legal-facts-used-in-messages).
3. Back up the database, then run migrations as a controlled step (`alembic upgrade head`). Every migration after `0001` is safe to re-run.
4. Deploy the backend, wait for `/health` to report `database: ok`, then deploy the frontend.
5. Smoke test: sign up, `/plan`, `/foods`, ask "Can I take paracetamol?" (it must refuse), and send "my baby is not moving" (it must say call 112).
6. Watch `GET /internal/metrics` and the logs for `chat.output_guard_blocked` and `chat.post_check_failed`: a spike means a rule or a source needs attention.

## Health and observability

`GET /health` checks database and Redis availability and returns 503 when degraded. Docker also validates its JSON status. Staff can inspect
`GET /internal/metrics`; metrics contain route counts and latency aggregates, not raw health
queries. Every response includes a request ID for correlation.
