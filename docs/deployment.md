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

## Cloud deployment (Vercel + Render + Neon)

A phone-reachable, always-on deployment (see the "Continue on phone" QR
feature in `AppShell.tsx`) needs a real public URL — Docker Compose on a
laptop only serves `localhost`. This path uses three free tiers, one per
concern, rather than a single VM:

- **Neon** — managed Postgres (`Lakebase Postgres`), replacing the
  `postgres` Compose service. Region `ap-southeast-1`, deliberately not
  `us-east-2`: this app's real users (Legal Metrology officers) are in
  India, and the ~200ms+ round-trip penalty `us-east-2` would add to every
  query isn't worth it for beta features (Object Storage, Functions, AI
  Gateway) this app doesn't use yet. Revisit only when one of those becomes
  an actual near-term task — and migrate before real inspection data
  accumulates, since Neon can't change a project's region in place.
  - CLI linked via `neon link` (project `ReguLens`, org `Arjun`) — see the
    git-ignored `.neon` file for the IDs.
  - `DATABASE_URL` / `DATABASE_URL_UNPOOLED` pulled into the root `.env`
    with `neon env pull -s postgres`. Only Postgres is pulled — this app
    doesn't use Neon Auth, Object Storage, or the AI Gateway.
  - Migrations always run against `DATABASE_URL_UNPOOLED` (direct, not
    pooled) — see the `neon-postgres` skill's pooled-vs-direct gotcha
    (pooled connections don't support the session-level operations
    migrations rely on). Wired into the app, not just a convention to
    remember: `Settings.database_url_unpooled` (optional — `None` for a
    plain single-endpoint Postgres with no pooled/unpooled split, e.g.
    local Docker Compose) and `alembic/env.py` prefers it over
    `database_url` when set. The app's own SQLAlchemy engine
    (`core/database.py`) always uses the regular pooled `database_url` —
    only the one-off migration step at container start needs the direct
    connection.
- **Render** — the backend, replacing the `backend` Compose service.
  Deploy via `render.yaml` at the repo root (Render's "New Blueprint"
  flow) rather than clicking through every field by hand. `DATABASE_URL`,
  `DATABASE_URL_UNPOOLED`, `JWT_SECRET_KEY`, and `CORS_ALLOWED_ORIGINS`
  are `sync: false` in that
  file — real secrets, entered in the Render dashboard, never committed.
  - The Dockerfile's `CMD` now runs `alembic upgrade head && python -m
    app.rules.loader && uvicorn ... --port ${PORT:-8000}` unconditionally
    (previously only Compose's `command:` override did this) — both steps
    are idempotent, so the image is correct standalone on Render (or any
    host) without a platform-specific Start Command, and `$PORT` expands
    to whatever Render assigns dynamically (falls back to 8000 when unset,
    e.g. a bare `docker run`).
  - **Known risk, not yet hit in practice**: the image bundles Playwright
    Chromium for scraping. Render's free tier is 512MB RAM — launching
    headless Chromium alongside Tesseract OCR under memory pressure can be
    flaky. Manual photo-scan/OCR-only flows are unaffected; automatic URL
    scraping might be occasionally unreliable. Fix, if it becomes a real
    problem, is a paid instance bump, not a re-architecture.
  - `STORAGE_ROOT` (uploaded images, generated reports) is on Render's
    free-tier ephemeral disk — wiped on redeploy/restart. Known gap, not
    yet fixed; Neon Object Storage is the identified fix (see the
    Cloud-deployment-vs-region note above), not yet implemented.
- **Vercel** — the frontend (static Vite build). Not yet deployed as of
  this writing; `VITE_API_BASE_URL` needs to point at Render's URL once
  it exists, and Render's `CORS_ALLOWED_ORIGINS` needs Vercel's domain
  added once *that* exists — a one-time chicken-and-egg step on first
  deploy of each side.

## What's NOT provided (be aware before treating this as production-ready)

- **No production/dev config split** for the Compose file beyond what's
  described above — Section 41 asks for "development and
  production-oriented configurations where practical"; V1 ships one
  Compose file suited to development and local demos. A production
  deployment would additionally need: TLS termination, a non-`--reload`
  Gunicorn/Uvicorn worker configuration with multiple workers, log
  aggregation, and secrets management beyond `.env` files / Render's
  dashboard — none of which are implemented here. (Managed Postgres with
  backups *is* covered now — see Neon, above.)
- **No CI/CD pipeline** is included in this repository.
- **Alembic migrations run automatically on container start** — fine for a
  single-instance demo, but a real production rollout would run migrations
  as a separate, gated step before scaling up new application instances.
- **`STORAGE_ROOT` is local disk** (a Docker volume in Compose, ephemeral
  disk on Render) — not object storage (S3/GCS/Neon Object Storage). Fine
  for one instance during dev; would need a shared/object store to run
  multiple backend replicas or to survive a Render redeploy.

## Environment variables

See `.env.example` at the repository root for the full, commented list
(database, JWT, CORS, storage, scraper, OCR). Never commit a real `.env`
file — it's git-ignored.
