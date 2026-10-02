# Configuration

Use `backend/.env.example` for a local SQLite API without Docker or provider keys. The root `.env.example` targets Docker Compose and uses container service names such as `db` and `redis`. Copy the example for your setup to its matching `.env` and set a unique JWT secret.

Every setting is an environment variable. The backend reads them (case-insensitive) from the process environment, then from `../.env` and `.env`. Copy [`.env.example`](../.env.example) to `backend/.env` to start. The defaults are meant to make the local demo run; production start-up **refuses the development JWT secret**.

## Backend

| Variable | Default | What it does |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` (or `prod`) switches on the production checks |
| `DEBUG` | `false` | Verbose errors. Never `true` in production |
| `DATABASE_URL` | `sqlite:///./matriva.db` | SQLite for local runs, PostgreSQL in production (`postgresql+psycopg://...`) |
| `VECTOR_DATABASE_URL` | unset | Where pgvector embeddings live (external engine only) |
| `REDIS_URL` | `redis://localhost:6379/0` | Shared rate limiting. Development can fall back locally; production startup rejects Redis outages and requests fail closed with 503 |
| `AUTO_CREATE_TABLES` | `true` | Create tables at start. Docker Compose sets it `false`: migrations are the schema authority |
| `DEMO_MODE` | `true` | Allows `/chat` without a token and the synthetic demo routes. **Set `false` in production** |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated exact origins. Never `*` with credentials |

### Authentication

| Variable | Default | What it does |
|---|---|---|
| `JWT_SECRET` | development value | At least 32 characters. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | `HS256` | Only HS256, HS384 or HS512 are accepted |
| `JWT_ISSUER` / `JWT_AUDIENCE` | `matriva-api` / `matriva-clients` | Checked on every token |
| `JWT_EXPIRES_MINUTES` | `30` | Between 5 and 1440 |

### Limits

| Variable | Default | What it does |
|---|---|---|
| `MAX_MESSAGE_CHARS` | `4000` | Longest chat message accepted (100 to 20000) |
| `MAX_UPLOAD_BYTES` | `10000000` | Largest admin document upload |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `20` | Sign-up and login attempts per client |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `30` | Chat messages per client |
| `RATE_LIMIT_GENERAL_PER_MINUTE` | `120` | Shared per-client quota across all other API routes, including care, profile, privacy, resources and admin. Health probes and CORS preflights are excluded |
| `EVALUATION_REPORT_DIR` | repository `evaluation/reports/` | Writable report directory. Docker uses `/app/runtime/evaluation/reports` on a persistent volume |

Configured Redis shares quotas across workers using an atomic increment and expiry. Local development without Redis uses a process-local fallback; production returns 503 when Redis quota storage is unavailable.

### Which engine answers

| Variable | Default | What it does |
|---|---|---|
| `RAG_ENGINE` | `local` | `local` is the offline pipeline: no model, no embeddings, no network. `external` is the Groq plus Gemini pipeline |
| `RAG_ORCHESTRATOR` | `langchain` | `langchain` composes the complete external query-to-response path with LangChain runnables. `native` is an explicit rollback/compatibility escape hatch |
| `LLM_PROVIDER` / `LLM_API_KEY` / `LLM_MODEL` | `groq` / empty / `openai/gpt-oss-120b` | Used only when `RAG_ENGINE=external` |
| `EMBEDDING_PROVIDER` / `EMBEDDING_API_KEY` / `EMBEDDING_MODEL` | `gemini` / empty / `models/gemini-embedding-001` | Used only when `RAG_ENGINE=external` |
| `TAVILY_API_KEY` | empty | Optional live web search for the external engine only. Web results are labelled as uncertain and never merged with reviewed sources |
| `INSTALL_OPTIONAL` | `false` | Compatibility Docker **build** argument. Provider packages use the main requirements pins in both modes; it cannot downgrade them |

Keep keys in a secret manager. Never put one in a variable that starts with `NEXT_PUBLIC_`: those are sent to the browser.

## Frontend

| Variable | Default | What it does |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | The backend's public URL. It is inlined into the client bundle **at build time**, so set it as a build argument too when you build the Docker image |

## Docker Compose

| Variable | Default | What it does |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `matriva` / `change-me` / `matriva` | The database. **Change the password** |
| `POSTGRES_PORT`, `REDIS_PORT` | `5432`, `6379` | Host ports |
| `BACKEND_PORT` | `8000` | Host port for the API (the README's local example uses 8010 instead) |
| `FRONTEND_PORT` | `3000` | Host port for the web app |
| `MATRIVA_ENV_FILE` | `.env` | Service environment file; disposable validation supplies synthetic configuration |

Not configurable by environment variable, because they are data: the guard-rail rules (`backend/app/data/guardrails/`), the care rules (`care_rules.yaml`), the food guide (`food_guide.yaml`) and the ontology. Change those in the YAML and run the tests.
