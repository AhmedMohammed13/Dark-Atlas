import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db

# Use SQLite for tests (no Docker needed)
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)

SAMPLE_ASSETS = [
    {
        "id": "a1",
        "type": "domain",
        "value": "example.com",
        "status": "active",
        "source": "scan",
        "tags": ["root"],
        "metadata": {},
    },
    {
        "id": "a2",
        "type": "subdomain",
        "value": "api.example.com",
        "status": "active",
        "source": "scan",
        "tags": ["prod"],
        "metadata": {},
    },
    {
        "id": "a3",
        "type": "certificate",
        "value": "cn=api.example.com",
        "status": "active",
        "source": "scan",
        "tags": [],
        "metadata": {"issuer": "Let's Encrypt", "expires": "2025-01-02"},
    },
]


def test_import_assets():
    response = client.post("/api/v1/import", json=SAMPLE_ASSETS)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 3
    assert data["updated"] == 0
    assert data["failed"] == 0


def test_import_idempotent():
    """Importing the same dataset twice must not create duplicates."""
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.post("/api/v1/import", json=SAMPLE_ASSETS)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert data["updated"] == 3


def test_import_partial_failure():
    """Bad record should not crash the whole batch."""
    bad_batch = [
        SAMPLE_ASSETS[0],
        {"type": "domain"},  # missing value and source
        SAMPLE_ASSETS[1],
    ]
    response = client.post("/api/v1/import", json=bad_batch)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["failed"] == 1
    assert len(data["errors"]) == 1


def test_list_assets():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.get("/api/v1/assets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3


def test_filter_by_type():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.get("/api/v1/assets?type=certificate")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["results"][0]["type"] == "certificate"


def test_filter_by_status():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.get("/api/v1/assets?status=active")
    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_get_single_asset():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.get("/api/v1/assets/a1")
    assert response.status_code == 200
    assert response.json()["value"] == "example.com"


def test_get_asset_not_found():
    response = client.get("/api/v1/assets/nonexistent")
    assert response.status_code == 404


def test_pagination():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)
    response = client.get("/api/v1/assets?page=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["total"] == 3
