"""Integration test fixtures: real FastAPI app against a throwaway Postgres DB.

The suite needs Postgres (models use postgres UUID columns). Locally:
`docker compose up db -d` — the test database is created automatically.
When Postgres is unreachable every test here is skipped, so a plain
`pytest tests/` still passes without Docker.
"""
import os
from urllib.parse import urlparse

import pytest

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://financeuser:financepass@localhost:5432/financedb_test",
)

# Must happen before `main` (and `database`) are imported by any fixture.
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["TESTING"] = "1"
os.environ.setdefault("JWT_SECRET_KEY", "integration-test-secret")

PASSWORD = "Str0ng-passw0rd!42"  # passes zxcvbn


def _ensure_test_db() -> bool:
    """Create the test database if missing. False when Postgres is down."""
    import psycopg2
    u = urlparse(TEST_DB_URL)
    dbname = u.path.lstrip("/")
    try:
        conn = psycopg2.connect(
            host=u.hostname, port=u.port or 5432, user=u.username,
            password=u.password, dbname="postgres", connect_timeout=3,
        )
    except Exception:
        return False
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if not cur.fetchone():
            cur.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        conn.close()
    return True


_DB_OK = _ensure_test_db()


def pytest_collection_modifyitems(config, items):
    if _DB_OK:
        return
    skip = pytest.mark.skip(reason="Postgres unavailable — start it with: docker compose up db -d")
    for item in items:
        if "tests/integration" in str(item.fspath).replace(os.sep, "/"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def app():
    import main  # imports run create_all + migrations against the test DB
    main.app.state.limiter.enabled = False  # rate limits would trip across tests
    return main.app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)  # fresh cookie jar per test


@pytest.fixture
def db(app):
    from database import SessionLocal
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _clean_tables(app):
    """Empty every table before each test so tests are order-independent."""
    from database import engine, Base
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture
def sent(monkeypatch):
    """Capture outbound emails (verification tokens, OTP codes, resets)."""
    captured = {}
    import auth_routes
    monkeypatch.setattr(auth_routes, "send_verification_email",
                        lambda email, token: captured.update(vtoken=token))
    monkeypatch.setattr(auth_routes, "send_otp_email",
                        lambda email, code: captured.update(otp=code))
    monkeypatch.setattr(auth_routes, "send_password_reset_email",
                        lambda email, token: captured.update(rtoken=token))
    return captured


@pytest.fixture
def make_user(client, sent):
    """Register + verify + login a user; returns (access_token, email)."""
    def _make(email="user@example.com", password=PASSWORD):
        r = client.post("/auth/register", json={"email": email, "password": password})
        assert r.status_code == 201, r.text
        r = client.post("/auth/verify-email", json={"token": sent["vtoken"]})
        assert r.status_code == 200, r.text
        r = client.post("/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return r.json()["access_token"], email
    return _make


@pytest.fixture
def auth_headers():
    return lambda token: {"Authorization": f"Bearer {token}"}
