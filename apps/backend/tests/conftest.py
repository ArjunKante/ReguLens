"""Shared pytest fixtures.

Tests run against a dedicated `<name>_test` Postgres database (never the dev
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

--- Test-database safety (P0 audit fix) -------------------------------------

This used to read `DATABASE_URL` via `os.environ.setdefault(...)`, which is
a no-op whenever `DATABASE_URL` is already set in the environment -- which
it always is under `docker compose run --rm backend pytest`, because
docker-compose.yml's `backend` service sets `DATABASE_URL` to the real
*dev* database (`lmscan`, not `lmscan_test`). That silently pointed this
suite's TRUNCATE-based isolation fixture at the shared dev database on
every single Docker-based test run, wiping real seeded/demo data — this
was hit repeatedly in practice, not a theoretical risk.

Fixed by never trusting the ambient `DATABASE_URL` at all: the test
database name is always derived from it (or from an explicit
`TEST_DATABASE_URL` override) by appending `_test`, and `DATABASE_URL` is
then force-overwritten in this process's environment *before* `app.core.database`
is imported anywhere (including transitively, e.g. by the FastAPI app under
test) — so the app's own module-level engine (used by the background
pipeline's own `SessionLocal()`, independent of any per-request session
override) resolves to the exact same safe test database, not the dev one.
A name-suffix assertion is kept as defense in depth even after that fix.
"""
from __future__ import annotations

import os
import uuid
import urllib.parse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session, sessionmaker


def _resolve_test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        url = explicit
    else:
        # Derive from whatever DATABASE_URL is already configured for this
        # environment (docker-compose's `postgres` hostname inside
        # containers, `.env`'s `localhost` for a bare local run) so the test
        # database is always reachable the same way the app itself would
        # reach its database, just under a different, obviously-test-only name.
        base = os.environ.get(
            "DATABASE_URL", "postgresql+psycopg://lmscan:lmscan_dev_pw@localhost:5432/lmscan"
        )
        head, _, db_name = base.rpartition("/")
        db_name = db_name.split("?", 1)[0]
        if not db_name.endswith("_test"):
            db_name = f"{db_name}_test"
        url = f"{head}/{db_name}"

    resolved_name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not resolved_name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {resolved_name!r} -- this suite "
            "truncates every application table after each test, so TEST_DATABASE_URL "
            "(or the DATABASE_URL it would otherwise be derived from) must name a "
            "database ending in '_test', e.g. "
            "postgresql+psycopg://user:pass@host:5432/lmscan_test."
        )
    return url


TEST_DATABASE_URL = _resolve_test_database_url()
# Force (not setdefault) -- everything imported after this line, including
# `app.core.database`'s module-level engine, must resolve to this same safe
# test database rather than whatever DATABASE_URL happened to be set to.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL


def _ensure_database_exists(url: str) -> None:
    """Creates the test database if it doesn't exist yet. CREATE DATABASE
    can't run against the database being created, so this connects to
    Postgres's own `postgres` maintenance database first."""
    parts = urllib.parse.urlsplit(url)
    db_name = parts.path.lstrip("/")
    maintenance_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    eng = create_engine(maintenance_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with eng.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).first()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    except ProgrammingError:
        pass  # created concurrently by another test process — fine
    finally:
        eng.dispose()


from app.core.database import Base  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.enums import RoleName  # noqa: E402
from app.models.user import Role, User  # noqa: E402
import app.models  # noqa: E402,F401 - ensure every model is registered on Base.metadata


@pytest.fixture(scope="session")
def engine():
    _ensure_database_exists(TEST_DATABASE_URL)
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
