# Deployment

## Docker Compose (development-oriented)

```bash
cp .env.example .env
# Fill in real POSTGRES_PASSWORD, JWT_SECRET_KEY (generate with
# `python -c "import secrets; print(secrets.token_urlsafe(48))"`), and any
# other values you want different from the defaults.

docker compose up --build
```

Services (`docker-compose.yml`):

- **postgres** — `postgres:16-alpine`, healthchecked, persistent volume
  (`lmscan_pg_data`).
- **backend** — built from `apps/backend/Dockerfile` (Python 3.11-slim +
  Tesseract OCR + every system library Playwright's Chromium needs,
  installed via `apt-get` and `playwright install --with-deps chromium`).
  Runs `alembic upgrade head`, then `python -m app.rules.loader` (idempotent
  — safe to run on every start), then `uvicorn`. Persistent volume
  `lmscan_storage` for uploaded/downloaded evidence and generated reports.
- **frontend** — multi-stage build: `node:20-alpine` builds the Vite app
  (`VITE_API_BASE_URL` passed as a build ARG), then `nginx:1.27-alpine`
  serves the static build with an SPA-friendly `try_files` config
  (`apps/frontend/nginx.conf`), so client-side routes like
  `/inspections/{id}` resolve correctly on a hard refresh.

Ports: backend `8000`, frontend `5173` (mapped to nginx's `80` inside the
container), postgres `5432`.

## Seeding demo accounts

```bash
docker compose exec backend python -m app.scripts.seed_demo_data
```

Creates the three demo accounts described in `docs/demo-guide.md`. Safe to
run more than once (idempotent — skips accounts that already exist).

## What's NOT provided (be aware before treating this as production-ready)

- **No production/dev config split** for the Compose file beyond what's
  described above — Section 41 asks for "development and
  production-oriented configurations where practical"; V1 ships one
  Compose file suited to development and local demos. A production
  deployment would additionally need: TLS termination, a non-`--reload`
  Gunicorn/Uvicorn worker configuration with multiple workers, a managed
  Postgres instance with backups, log aggregation, and secrets management
  (not `.env` files) — none of which are implemented here.
- **No CI/CD pipeline** is included in this repository.
- **Alembic migrations run automatically on container start** — fine for a
  single-instance demo, but a real production rollout would run migrations
  as a separate, gated step before scaling up new application instances.
- **`STORAGE_ROOT` is a local Docker volume**, not object storage (S3/GCS).
  Fine for one instance; would need a shared/object store to run multiple
  backend replicas.

## Environment variables

See `.env.example` at the repository root for the full, commented list
(database, JWT, CORS, storage, scraper, OCR). Never commit a real `.env`
file — it's git-ignored.
