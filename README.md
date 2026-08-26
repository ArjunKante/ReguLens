# LM-SCAN V1

**AI-Assisted Online Legal Metrology Compliance Inspection System**

LM-SCAN is a preliminary, AI-assisted compliance-screening tool that helps an
authorized Legal Metrology officer inspect a packaged-commodity product
listing on an online marketplace/quick-commerce platform. It retrieves a
public product listing, extracts declarations from page text, structured
metadata, and product images (via OCR), evaluates them against a
source-traceable rule database derived from the Legal Metrology (Packaged
Commodities) Rules, 2011, flags potential issues with evidence and
confidence scores, and lets an officer review and finalize findings before
generating a report.

> ⚠️ **LM-SCAN is not a legally binding decision maker.** Every automated
> finding is explicitly labeled `PASS`, `POTENTIAL_NON_COMPLIANCE`,
> `NEEDS_MANUAL_REVIEW`, `NOT_APPLICABLE`, or `UNABLE_TO_VERIFY`, and every
> report carries the disclaimer *"Automated Preliminary Compliance
> Assessment — Subject to Verification by an Authorized Officer."*

**Version 1 scope:** online listing inspection only (Section 2 of the
product brief). Physical-package measurement (camera/calibration) is
explicitly out of scope for V1 — see [`docs/limitations.md`](docs/limitations.md)
and [`docs/architecture.md`](docs/architecture.md#future-physical-inspection-module)
for how the architecture leaves room for it.

## Documentation

| Doc | Contents |
|---|---|
| [`docs/legal-rules.md`](docs/legal-rules.md) | The structured, source-traceable rule database — every implemented rule, its statutory citation, and what's explicitly out of scope |
| [`docs/architecture.md`](docs/architecture.md) | System design, module boundaries, data flow |
| [`docs/api.md`](docs/api.md) | REST API reference |
| [`docs/scraper.md`](docs/scraper.md) | Scraping subsystem design, adapters, safety/legality controls |
| [`docs/ocr.md`](docs/ocr.md) | OCR subsystem, engines, image quality checks |
| [`docs/compliance-engine.md`](docs/compliance-engine.md) | Rule engine, validators, status logic, consistency engine |
| [`docs/dataset.md`](docs/dataset.md) | Fixtures, evaluation methodology, measured results |
| [`docs/testing.md`](docs/testing.md) | How to run the test suites, what's covered |
| [`docs/deployment.md`](docs/deployment.md) | Docker/production notes |
| [`docs/limitations.md`](docs/limitations.md) | Honest list of what V1 does not do |
| [`docs/demo-guide.md`](docs/demo-guide.md) | Step-by-step demo script |

## Repository layout

```
apps/
  backend/          FastAPI + SQLAlchemy + Alembic (Python 3.11)
    app/
      api/routes/    HTTP endpoints
      auth/          JWT auth + RBAC dependencies
      compliance/    Compliance engine + consistency engine
      core/          Config, DB session, security primitives
      models/        SQLAlchemy ORM models
      nlp/           Declaration extraction, classification, normalization
      ocr/           Pluggable OCR engines (Tesseract wired, PaddleOCR adapter)
      reports/       Report rendering (Jinja2 -> HTML/PDF)
      repositories/  DB query helpers
      rules/         Rule seed data, validators, versioning loader
      scraping/       ProductScraper interface + Generic/Blinkit/Amazon/Flipkart adapters
      services/      Pipeline orchestration, glue services
      storage/       Safe file storage
      vision/        Image quality + preprocessing
    alembic/         DB migrations
    tests/           pytest suite (unit + integration), HTML fixtures
  frontend/          React + TypeScript (Vite)
    src/
      api/           Typed API client
      components/    Shared UI components
      context/       Auth context
      pages/         Route-level pages
    tests/           Vitest + React Testing Library
legal/               Authoritative source PDF (Legal Metrology Rules, 2011)
docs/                Documentation (see table above)
data/                Sample fixtures / evaluation notes (docs/dataset.md)
docker-compose.yml   backend + frontend + postgres
```

## Quick start (local, without Docker)

### Prerequisites

- Python 3.11
- Node.js 20+
- PostgreSQL 16 (a local instance, or run `docker compose up postgres`)
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) binary installed and on PATH (or set `TESSERACT_CMD` to its full path)

### 1. Environment

```bash
cp .env.example .env
# Edit .env: set POSTGRES_*, DATABASE_URL, JWT_SECRET_KEY (generate with
# `python -c "import secrets; print(secrets.token_urlsafe(48))"`), and
# TESSERACT_CMD if tesseract isn't on PATH.
```

### 2. Database

```bash
# Create the database (adjust to your local Postgres setup):
createdb lmscan

cd apps/backend
python -m venv .venv
.venv/Scripts/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m playwright install chromium
alembic upgrade head
python -m app.rules.loader          # loads the source-traceable rule database
python -m app.scripts.seed_demo_data  # creates roles + demo accounts (see docs/demo-guide.md)
```

### 3. Backend

```bash
cd apps/backend
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 4. Frontend

```bash
cd apps/frontend
cp .env.example .env   # VITE_API_BASE_URL, defaults to http://localhost:8000/api/v1
npm install
npm run dev
# App: http://localhost:5173
```

## Tests

```bash
# Backend (44 tests: unit + integration, real Postgres test DB, no live network)
cd apps/backend
python -m pytest tests/ -v

# Frontend (10 tests: Vitest + React Testing Library)
cd apps/frontend
npm run test

# Lint / type-check
cd apps/backend && ruff check app/ tests/ && mypy app/ --ignore-missing-imports
cd apps/frontend && npm run lint && npm run build   # build runs tsc -b (type-check)
```

See [`docs/testing.md`](docs/testing.md) for full details and exact results from the last run.

## Docker

```bash
cp .env.example .env   # fill in real secrets
docker compose up --build
# frontend: http://localhost:5173  backend: http://localhost:8000
```

See [`docs/deployment.md`](docs/deployment.md).

## License / academic context

This is an academic prototype (Version 1) built against a supplied legal
source document. It is not deployed, not certified, and not a substitute
for legal advice or an authorized officer's judgment.
