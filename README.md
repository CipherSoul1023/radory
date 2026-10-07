# Radory

Radory is a commercial real estate lead intelligence platform for tenant-rep brokers. This repository is a modular monolith with a React frontend, a FastAPI backend, and a Celery worker. It currently contains only development infrastructure and a minimal application shell. Product features are not implemented.

## Prerequisites

- Node.js 22 (22.18 or newer) and npm 10
- Python 3.12, managed through [uv](https://docs.astral.sh/uv/)
- Docker Engine with the Docker Compose plugin, or Docker Desktop, for the full local stack

On Windows PowerShell, use `npm.cmd` if `npm.ps1` is blocked by the execution policy. The commands below use `npm` for portability.

If Docker Desktop is installed but `docker` is not on PATH in PowerShell, use the included wrapper in place of `docker`:

```powershell
.\scripts\docker.cmd compose up --build
```

## Environment

Run once from the repository root:

```sh
uv run --no-project --python 3.12 --cache-dir .uv-cache scripts/init_env.py
```

This creates ignored `.env` and `frontend/.env.local` files and never overwrites existing files. It generates a password only for the optional local PostgreSQL fallback. The root [.env.example](.env.example) documents backend and Compose variables; [frontend/.env.example](frontend/.env.example) documents browser variables. Keep real credentials in `.env` and `frontend/.env.local`, never in the examples.

Normal development uses managed infrastructure. Set root `DATABASE_URL` to the Neon PostgreSQL connection string and `REDIS_URL` to the Upstash `rediss://` connection string. Compose passes both values unchanged to FastAPI and Celery. Browser configuration belongs only in `frontend/.env.local` under explicit `VITE_*` names.

## Full stack with Docker

```sh
docker compose up --build
```

Open the frontend at <http://localhost:5173> and the API health endpoint at <http://localhost:8001/health>. The default stack starts FastAPI, Celery, and the Vite frontend. FastAPI and Alembic use Neon through `DATABASE_URL`; FastAPI and Celery use Upstash through `REDIS_URL`. The first run builds images and installs locked dependencies.

Useful commands from the repository root:

| Task | Command |
| --- | --- |
| Start stack | `docker compose up --build` |
| Stop stack | `docker compose down` |
| Rebuild stack | `docker compose build` |
| View logs | `docker compose logs -f` |
| Check API | `curl http://localhost:8001/health/ready` |
| Check worker | `docker compose exec worker celery -A app.workers.celery_app:celery_app inspect ping` |

Once the services are healthy, apply the initial migration:

```sh
docker compose exec backend alembic upgrade head
```

This applies migrations to the configured Neon database. The initial revision has no product tables. Later migrations should be generated from SQLAlchemy metadata, reviewed, and committed. Do not use `create_all()` for schema management.

## Optional local infrastructure

Local PostgreSQL and Redis remain available for fallback and isolated testing, but the application does not depend on them. Start them explicitly with:

```sh
docker compose --profile local-infra up -d postgres redis
```

They listen on `LOCAL_POSTGRES_PORT` (default 5434) and `LOCAL_REDIS_PORT` (default 6380). To run application processes against them, explicitly supply local `DATABASE_URL` and `REDIS_URL` values for that run. The default `docker compose up` continues to use the managed URLs from `.env` and does not start these services.

## Run application processes on the host

Application processes can also run on the host against the same managed services:

```sh
cd frontend
npm ci
npm run dev
```

In separate terminals from the repository root:

```sh
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8001
```

```sh
cd backend
uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

The Celery worker requires a Unix-like environment; on Windows, use the Docker worker for a reliable local run. The API and frontend can run directly on Windows.

## Developer commands

Run frontend commands in `frontend/` and backend commands in `backend/`:

| Task | Command |
| --- | --- |
| Frontend dev server | `npm run dev` |
| Frontend production build | `npm run build` |
| Frontend lint | `npm run lint` |
| Frontend format | `npm run format` |
| Backend dev server | `uv run uvicorn app.main:app --reload --port 8001` |
| Backend tests | `uv run pytest` |
| Backend lint | `uv run ruff check .` |
| Backend format | `uv run ruff format .` |
| Check backend formatting | `uv run ruff format --check .` |
| Create migration | `uv run alembic revision --autogenerate -m "description"` |
| Apply migrations | `uv run alembic upgrade head` |
| Roll back one migration | `uv run alembic downgrade -1` |
| Start Celery worker | `uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info` |

The lockfiles are `frontend/package-lock.json` and `backend/uv.lock`. Commit both whenever dependencies change. Use `npm ci` and `uv sync --frozen` to reproduce them.

## Health checks

`GET /health` confirms FastAPI is running. `GET /health/ready` checks PostgreSQL and Redis. In the development environment only, `POST /health/tasks` enqueues a small Celery task and returns a task ID; `GET /health/tasks/{task_id}` reports its status and result. For example:

```sh
curl -X POST http://localhost:8001/health/tasks
curl http://localhost:8001/health/tasks/TASK_ID
```

A successful result is `{"status":"SUCCESS","result":"ok"}`. The task endpoints return 404 outside development.

## External credentials

No external accounts are required for local bootstrap. When ready to connect providers, enter the following in the ignored files:

| Provider | Location and variables |
| --- | --- |
| Tavily | `.env`: `TAVILY_API_KEY` |
| Nebius / NVIDIA Nemotron | `.env`: `NEBIUS_API_KEY`, `NEBIUS_BASE_URL`, `NEMOTRON_NANO_MODEL`, `NEMOTRON_SUPER_MODEL`, `NEMOTRON_ULTRA_MODEL`; legacy `NEMOTRON_MODEL` is an optional fallback |
| Clerk | `.env`: `CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `CLERK_ISSUER` (optional `CLERK_JWKS_URL`, `CLERK_AUDIENCE`); `frontend/.env.local`: `VITE_CLERK_PUBLISHABLE_KEY` |
| Neon | `.env`: `DATABASE_URL` for normal development |
| Upstash | `.env`: `REDIS_URL` using a Celery-compatible `rediss://` URL for normal development |
| Cloudflare R2 | `.env`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` (optional `R2_ENDPOINT`) |
| PostHog | `.env`: `POSTHOG_API_KEY`, `POSTHOG_HOST`; `frontend/.env.local`: `VITE_POSTHOG_KEY`, `VITE_POSTHOG_HOST` |
| Sentry | `.env`: `SENTRY_DSN`; `frontend/.env.local`: `VITE_SENTRY_DSN` |

For Docker Compose and direct `npm run dev`, Vite loads browser-safe values from `frontend/.env.local`. Backend variables are not mapped or copied into Vite. `SENTRY_DSN` belongs to FastAPI and Celery; `VITE_SENTRY_DSN` belongs to the separate frontend Sentry project. Vercel deployment credentials are not needed for local development.

Provider clients are lazy and do not call their services during startup. Optional integrations stay disabled until configured.

## Troubleshooting

- If the optional local PostgreSQL service needs credentials, run `scripts/init_env.py` as shown above or configure the local-only PostgreSQL variables. Existing `.env` files are preserved.
- If `/health/ready` returns 503, check `docker compose ps` and PostgreSQL/Redis logs.
- If a task stays `PENDING`, check `docker compose logs worker` and confirm Redis is healthy.
- If the managed stack cannot connect to PostgreSQL or Redis, confirm `.env` contains valid Neon `DATABASE_URL` and Upstash `REDIS_URL` values and that outbound TLS access is available.
- For optional local infrastructure, start `docker compose --profile local-infra up -d postgres redis` and explicitly provide local connection URLs to the application process being tested.
- If npm or uv cannot download packages, check registry access and retry `npm ci` or `uv sync --frozen`.
