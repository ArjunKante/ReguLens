"""Shared pytest fixtures.

Tests run against a dedicated `lmscan_test` Postgres database (never the dev
or prod database) so the full ORM/constraint stack is exercised, matching
the deployment target (Section 21: PostgreSQL).

Isolation strategy: each test's `db` fixture commits for real (not just a
rolled-back SAVEPOINT). This is deliberate, not an oversight — several
integration tests exercise FastAPI BackgroundTasks (the inspection
pipeline), which opens its own database connection independent of the
request's session; a SAVEPOINT-based rollback fixture would make those rows
invisible to that second connection under Postgres's READ COMMITTED
isolation, since an uncommitted transaction on one connection is never
visible to another. Instead, an autouse fixture truncates every
application table after each test, so state never leaks between tests even
though each one commits directly.

Live network access (scraping a real marketplace, live OCR against a real
image) is NEVER exercised by this suite — see the `download_image`/
`get_scraper_for_url` monkeypatches in the integration tests (Section 36).
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://lmscan:lmscan_dev_pw@localhost:5434/lmscan_test"
)

from app.core.database import Base  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import RoleName  # noqa: E402
from app.models.user import Role, User  # noqa: E402
import app.models  # noqa: E402,F401 - ensure every model is registered on Base.metadata

TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Session:  # type: ignore[no-untyped-def]
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        _truncate_all_tables(engine)


def _truncate_all_tables(engine) -> None:  # type: ignore[no-untyped-def]
    table_names = [t.name for t in reversed(Base.metadata.sorted_tables)]
    if not table_names:
        return
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def roles(db: Session) -> dict[str, Role]:
    result = {}
    for name in RoleName:
        role = Role(name=name)
        db.add(role)
        db.flush()
        result[name.value] = role
    db.commit()
    return result


@pytest.fixture()
def inspector_user(db: Session, roles: dict[str, Role]) -> User:
    user = User(
        email=f"inspector-{uuid.uuid4().hex[:8]}@lmscan.example",
        hashed_password=hash_password("TestPassword!123"),
        full_name="Test Inspector",
        role_id=roles["INSPECTOR"].id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_user(db: Session, roles: dict[str, Role]) -> User:
    user = User(
        email=f"admin-{uuid.uuid4().hex[:8]}@lmscan.example",
        hashed_password=hash_password("TestPassword!123"),
        full_name="Test Admin",
        role_id=roles["ADMIN"].id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
