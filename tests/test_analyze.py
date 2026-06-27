import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch, MagicMock

from app.main import app
from app.db.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///./test_analyze.db"

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
        "type": "certificate",
        "value": "cn=api.example.com",
        "status": "active",
        "source": "scan",
        "tags": [],
        "metadata": {"issuer": "Let's Encrypt", "expires": "2025-01-02"},
    },
]


def test_analyze_invalid_mode():
    response = client.post("/api/v1/analyze", json={"mode": "unknown_mode"})
    assert response.status_code == 400


def test_analyze_nl_query_missing_input():
    response = client.post("/api/v1/analyze", json={"mode": "nl_query"})
    assert response.status_code == 400


def test_analyze_enrich_missing_asset_id():
    response = client.post("/api/v1/analyze", json={"mode": "enrich"})
    assert response.status_code == 400


def test_analyze_nl_query_with_mock():
    """Test NL query returns only real DB data."""
    client.post("/api/v1/import", json=SAMPLE_ASSETS)

    mock_filters = {"type": "certificate", "status": None, "tags": None, "value_contains": None}

    with patch("app.ai.chains.nl_query.NLQueryChain.run") as mock_run:
        mock_run.return_value = {
            "question": "show me all certificates",
            "filters_used": mock_filters,
            "count": 1,
            "results": [{"id": "a2", "type": "certificate", "value": "cn=api.example.com"}],
        }
        response = client.post(
            "/api/v1/analyze",
            json={"mode": "nl_query", "input": "show me all certificates"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


def test_analyze_risk_score_with_mock():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)

    with patch("app.ai.chains.risk_scoring.RiskScoringChain.run") as mock_run:
        mock_run.return_value = {
            "risk_score": 75,
            "risk_level": "high",
            "findings": [],
            "summary": "Test summary",
            "recommendations": [],
        }
        response = client.post("/api/v1/analyze", json={"mode": "risk_score"})
        assert response.status_code == 200
        assert response.json()["risk_score"] == 75


def test_analyze_report_with_mock():
    client.post("/api/v1/import", json=SAMPLE_ASSETS)

    with patch("app.ai.chains.report_gen.ReportGenChain.run") as mock_run:
        mock_run.return_value = {
            "total_assets": 2,
            "by_type": {"domain": 1, "certificate": 1},
            "by_status": {"active": 2},
            "report": "Test report content",
        }
        response = client.post("/api/v1/analyze", json={"mode": "report", "filters": {}})
        assert response.status_code == 200
        assert "report" in response.json()
