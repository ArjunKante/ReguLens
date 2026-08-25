"""End-to-end API workflow test (Section 34/52): login -> create inspection
-> scan URL (mocked scraper, no live network) -> poll status -> review a
finding -> generate a report -> dashboard statistics -> rule listing.

This exercises the acceptance-criteria workflow through the real HTTP layer
(FastAPI TestClient), the real Postgres test database, and the real
compliance engine — only the network-facing scrape/download calls are
stubbed, per Section 36.
"""
from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from app.models.enums import RoleName
from app.models.user import Role, User
from app.rules.loader import load_rules
from app.scraping.blinkit import BlinkitScraper
from app.scraping.fetcher import StaticHTMLFetcher
from app.services import pipeline as pipeline_module

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "html"


def _client(db: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _create_user(db: Session, role_name: RoleName, email: str, password: str) -> User:
    role = db.query(Role).filter(Role.name == role_name).one_or_none()
    if role is None:
        role = Role(name=role_name)
        db.add(role)
        db.commit()
    user = User(email=email, hashed_password=hash_password(password), full_name=f"Test {role_name.value}", role_id=role.id)
    db.add(user)
    db.commit()
    return user


def test_full_officer_workflow(db: Session, monkeypatch):
    load_rules(db)
    _create_user(db, RoleName.INSPECTOR, "wf-inspector@lmscan.example", "TestPassword!123")
    _create_user(db, RoleName.REVIEWER, "wf-reviewer@lmscan.example", "TestPassword!123")
    _create_user(db, RoleName.ADMIN, "wf-admin@lmscan.example", "TestPassword!123")

    html = (FIXTURES / "missing_declaration.html").read_text(encoding="utf-8")
    monkeypatch.setattr(
        "app.services.scraping_service.get_scraper_for_url",
        lambda u: BlinkitScraper(fetcher=StaticHTMLFetcher(html=html, url=u)),
    )
    monkeypatch.setattr(pipeline_module, "download_image", lambda url: None)

    client = _client(db)

    # --- login ---
    resp = client.post("/api/v1/auth/login", json={"email": "wf-inspector@lmscan.example", "password": "TestPassword!123"})
    assert resp.status_code == 200, resp.text
    inspector_token = resp.json()["access_token"]
    inspector_headers = {"Authorization": f"Bearer {inspector_token}"}

    resp = client.post("/api/v1/auth/login", json={"email": "wf-reviewer@lmscan.example", "password": "TestPassword!123"})
    reviewer_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post("/api/v1/auth/login", json={"email": "wf-admin@lmscan.example", "password": "TestPassword!123"})
    admin_headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    # --- reviewer cannot create inspections (RBAC enforced server-side) ---
    resp = client.post("/api/v1/inspections", json={"source_url": "https://blinkit.com/prn/x/prid/1"}, headers=reviewer_headers)
    assert resp.status_code == 403

    # --- create inspection ---
    resp = client.post("/api/v1/inspections", json={"source_url": "https://blinkit.com/prn/x/prid/1"}, headers=inspector_headers)
    assert resp.status_code == 201, resp.text
    inspection_id = resp.json()["id"]

    # --- scan url (runs pipeline synchronously in TestClient's background tasks) ---
    resp = client.post(f"/api/v1/inspections/{inspection_id}/scan-url", headers=inspector_headers)
    assert resp.status_code == 202, resp.text

    # TestClient runs BackgroundTasks synchronously before returning the response
    # in Starlette, but our task opens a NEW session (SessionLocal), so give it a
    # brief moment and then re-query through the same test db session.
    for _ in range(20):
        resp = client.get(f"/api/v1/inspections/{inspection_id}", headers=inspector_headers)
        if resp.json()["status"] == "COMPLETED":
            break
        time.sleep(0.2)

    detail = resp.json()
    assert detail["status"] == "COMPLETED"
    assert detail["overall_status"] in ("POTENTIAL_NON_COMPLIANCE", "NEEDS_MANUAL_REVIEW", "UNABLE_TO_VERIFY", "PASS")
    assert len(detail["compliance_checks"]) > 0

    # --- declarations endpoint ---
    resp = client.get(f"/api/v1/inspections/{inspection_id}/declarations", headers=inspector_headers)
    assert resp.status_code == 200

    # --- find a POTENTIAL_NON_COMPLIANCE check and review it ---
    flagged = [c for c in detail["compliance_checks"] if c["status"] == "POTENTIAL_NON_COMPLIANCE"]
    assert flagged, "missing_declaration.html fixture should trigger at least one POTENTIAL_NON_COMPLIANCE"
    check_id = flagged[0]["id"]

    resp = client.post(
        f"/api/v1/inspections/{inspection_id}/review",
        json={"compliance_check_id": check_id, "decision": "CONFIRM", "comment": "Verified manually."},
        headers=reviewer_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "CONFIRM"
    assert resp.json()["automated_status"] == "POTENTIAL_NON_COMPLIANCE"

    # --- inspector cannot submit reviews (RBAC) ---
    resp = client.post(
        f"/api/v1/inspections/{inspection_id}/review",
        json={"compliance_check_id": check_id, "decision": "REJECT"},
        headers=inspector_headers,
    )
    assert resp.status_code == 403

    # --- generate report ---
    resp = client.post(f"/api/v1/inspections/{inspection_id}/report?fmt=HTML", headers=inspector_headers)
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["report_id"]

    resp = client.get(f"/api/v1/reports/{report_id}/download", headers=inspector_headers)
    assert resp.status_code == 200
    assert b"LM-SCAN" in resp.content
    assert b"Subject to Verification" in resp.content

    # --- dashboard statistics ---
    resp = client.get("/api/v1/dashboard/statistics", headers=inspector_headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_online_inspections"] >= 1

    # --- rules listing ---
    resp = client.get("/api/v1/rules", headers=inspector_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 14

    # --- admin can create a user, inspector cannot ---
    resp = client.post(
        "/api/v1/users",
        json={"email": "new-reviewer@lmscan.example", "password": "AnotherPass!123", "full_name": "New Reviewer", "role": "REVIEWER"},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text

    resp = client.post(
        "/api/v1/users",
        json={"email": "blocked@lmscan.example", "password": "AnotherPass!123", "full_name": "Blocked", "role": "REVIEWER"},
        headers=inspector_headers,
    )
    assert resp.status_code == 403

    app.dependency_overrides.clear()
