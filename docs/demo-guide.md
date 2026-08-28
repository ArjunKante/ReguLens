# Demo Guide

Step-by-step script for demonstrating LM-SCAN V1.

## 1. Start everything

```bash
# Terminal 1 — database (if not already running)
docker compose up postgres

# Terminal 2 — backend
cd apps/backend
alembic upgrade head
python -m app.rules.loader
python -m app.scripts.seed_demo_data
uvicorn app.main:app --reload --port 8000

# Terminal 3 — frontend
cd apps/frontend
npm run dev
```

Open `http://localhost:5173`.

## 2. Demo accounts

`python -m app.scripts.seed_demo_data` creates three accounts (clearly
labeled as demo-only, never real credentials — see the script's
docstring):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@lmscan.demo` | `AdminDemo!2026` |
| Inspector | `inspector@lmscan.demo` | `InspectorDemo!2026` |
| Reviewer | `reviewer@lmscan.demo` | `ReviewerDemo!2026` |

## 3. Core workflow (log in as Inspector)

1. **Log in** as `inspector@lmscan.demo`.
2. **Dashboard** — shows all-zero stats on a fresh database; this fills in
   as inspections are created.
3. **New Inspection** → paste a product listing URL → **Start scan**.
   - A real marketplace URL (e.g. a Blinkit product page) exercises the
     full Playwright fetch → JSON-LD/OpenGraph/CSS-selector/fallback-text
     extraction → image download → OCR path.
   - If you don't want to depend on a live marketplace being reachable
     during a demo, `https://example.com/` is a safe, ToS-clean way to show
     the mechanism end-to-end (real fetch, real robots.txt check, real
     pipeline) — it will correctly produce mostly
     `POTENTIAL_NON_COMPLIANCE`/`UNABLE_TO_VERIFY` findings since it isn't
     a product page, which is itself a good demonstration of the
     evidence-quality-aware status logic.
4. You land on the **Inspection Detail** page mid-pipeline — the
   **Analysis progress** panel polls and updates live (Section 43's exact
   UX: "Fetching page… → Extracting… → Running OCR… → ... → Analysis
   complete").
5. Once `COMPLETED`, the page shows:
   - The disclaimer banner (Section 17's required wording).
   - Findings grouped by status (`POTENTIAL_NON_COMPLIANCE` first), each
     card showing the rule title, `rule_key`, statutory reference, source
     document/locator, rule version, the plain-language reason, a
     confidence bar, and an expandable evidence list.
   - Extracted declarations (field, value, source type, confidence).
   - Product images with quality flags.
   - **Generate Report** (PDF or HTML) — downloads through the
     authenticated API client.
6. If the URL couldn't be retrieved: the page shows *"Automatic page
   extraction unavailable"* with a screenshot-upload control — upload one
   or more images and click **Upload screenshots & re-analyze** to continue
   the same inspection via the fallback path.

## 4. Review workflow (log in as Reviewer)

1. Log out, log in as `reviewer@lmscan.demo`.
2. Open the same inspection from **Inspection History**.
3. On any `POTENTIAL_NON_COMPLIANCE` (or other) finding, click **Review
   this finding** → choose a decision (`CONFIRM` / `REJECT` / `OVERRIDE` /
   `REQUEST_MORE_EVIDENCE`), a final status, and an optional comment →
   **Submit review decision**.
4. Note the finding now shows both the original automated result and the
   reviewer's decision — the automated result is never overwritten
   (Section 16).
5. Log in as `inspector@lmscan.demo` again and confirm the **Review**
   button/action is not available to that role (RBAC enforced
   server-side — try `POST /inspections/{id}/review` directly as an
   inspector via `/docs` and note the `403`).

## 5. Admin workflow

1. Log in as `admin@lmscan.demo`.
2. **User Management** — create a new user with any role.
3. **Rule Management** — browse all 25 rules (19 legal + 6 consistency),
   expand one to see its full requirement text, applicability, exceptions,
   and source citation.
4. Via `/docs` (Swagger UI), demonstrate `PUT /rules/{rule_key}` updating a
   rule's `notes` field, then reload the Rule Management page and note the
   version number incremented — and that a *previous* inspection's report
   (regenerate it) still cites the *old* version number, demonstrating
   Section 12's rule-versioning guarantee.

## 6. Dashboard

Return to **Dashboard** after a few inspections exist — stat tiles,
inspections-by-platform/category, most-common-issues, violations-by-rule,
and recent inspections all populate from real data (Section 18).

## 7. What to say about scope

If asked "does this measure the physical package?" — no, by design (see
the product brief's Section 2 scope decision and `docs/architecture.md`'s
"Future physical inspection module" section, which explains how the
existing evidence/rule/compliance/report architecture would absorb a
physical module without rewrites).
