# API Reference

Base path: `/api/v1` (configurable via `API_V1_PREFIX`). Full interactive
OpenAPI docs are served at `/docs` (Swagger UI) and `/redoc` whenever the
backend is running — this file is a narrative companion, not a generated
spec.

All endpoints except `POST /auth/login` require `Authorization: Bearer
<token>`. Roles are `ADMIN`, `INSPECTOR`, `REVIEWER`; permission checks are
enforced server-side in `app/auth/dependencies.py`, never only in the
frontend (Section 20).

## Auth

### `POST /auth/login`
Body: `{"email": str, "password": str}`.
Returns `{access_token, token_type, role, full_name, user_id}`. Failures are
logged to `audit_logs` (`LOGIN_FAILED` / `LOGIN_SUCCESS`).

## Users (ADMIN only)

- `GET /users` — list all users.
- `POST /users` — create a user. Body: `{email, password, full_name, role}`.

## Inspections

- `POST /inspections` *(ADMIN, INSPECTOR)* — create an inspection shell.
  Body: `{source_url, notes?}`. Returns `201` with an `InspectionSummary`.
- `GET /inspections` — list inspections. Query params: `status`,
  `overall_status`, `platform`, `mine_only`, `limit`, `offset`.
- `GET /inspections/{id}` — full detail: declarations, compliance checks
  (with rule citation, evidence, violation, review decisions), images,
  web pages, pipeline events.
- `POST /inspections/{id}/scan-url` *(ADMIN, INSPECTOR)* — triggers the full
  pipeline (FETCH → ... → REPORT-readiness) as a background task. Returns
  `202 Accepted` immediately; poll `GET /inspections/{id}` for progress via
  `pipeline_events` (Section 30/43).
- `POST /inspections/{id}/screenshots` *(ADMIN, INSPECTOR)* — multipart
  upload of one or more images (`files`), used when automatic retrieval
  failed (Section 5/25). Validates MIME/extension/size
  (`app/storage/files.py`), assesses image quality, does **not** run OCR
  synchronously.
- `POST /inspections/{id}/analyze` *(ADMIN, INSPECTOR)* — (re-)runs the
  pipeline, typically after uploading screenshots.
- `POST /inspections/{id}/declarations` *(ADMIN, INSPECTOR)* — add a manual
  declaration (`USER_INPUT` source type). Body: `{field_name, value}`.
- `GET /inspections/{id}/declarations` — list extracted declarations.
- `GET /inspections/{id}/compliance` — list compliance checks.
- `POST /inspections/{id}/review` *(ADMIN, REVIEWER)* — submit a review
  decision. Body: `{compliance_check_id, decision, final_status?, comment?,
  reason?, additional_evidence?}`. `decision` is one of `CONFIRM`,
  `REJECT`, `OVERRIDE`, `REQUEST_MORE_EVIDENCE`. The automated result is
  never overwritten — a new `review_decisions` row is appended
  (Section 16).
- `POST /inspections/{id}/report?fmt=PDF|HTML` — generates a report,
  returns `{report_id, format, generated_at, download_url}`.

## Reports

- `GET /reports/{report_id}/download` — streams the generated file
  (`application/pdf` or `text/html`). Requires the Bearer token — the
  frontend fetches this through its authenticated API client and opens a
  local object URL, since a bare `<a href>` to this endpoint would 401.

## Rules

- `GET /rules` — list every rule with its current version.
- `GET /rules/{rule_key}/versions` — full version history for one rule.
- `POST /rules` *(ADMIN)* — create a new rule (first `RuleVersion`).
- `PUT /rules/{rule_key}` *(ADMIN)* — update a rule's content; creates a
  new `RuleVersion` if content actually changed (no-op otherwise), leaving
  historical `ComplianceCheck` rows pointing at the old version
  (Section 12).

## Dashboard

- `GET /dashboard/statistics` — totals by status, by platform, by category,
  violations by rule, most common issues, review backlog, 30-day trend
  (Section 18).

## Status vocabulary

Every `ComplianceCheck.status` and `Inspection.overall_status` is one of:

| Status | Meaning |
|---|---|
| `PASS` | Requirement found satisfied with adequate evidence |
| `POTENTIAL_NON_COMPLIANCE` | Requirement appears unmet on otherwise-complete evidence — needs officer verification, not a confirmed violation |
| `NEEDS_MANUAL_REVIEW` | Evidence is incomplete/low-quality, or the requirement is inherently a human judgment call |
| `NOT_APPLICABLE` | Rule does not apply (category exclusion, exemption, no importer identified, etc.) |
| `UNABLE_TO_VERIFY` | Insufficient evidence exists to evaluate the rule at all |

See `docs/compliance-engine.md` for exactly how each status is chosen.
