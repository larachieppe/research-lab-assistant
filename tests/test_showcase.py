import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import Settings
from web import db
from web.app import app


def _settings(**overrides) -> Settings:
    defaults = dict(
        anthropic_api_key="dummy",
        anthropic_model="claude-sonnet-5",
        ncbi_api_key=None,
        ncbi_email=None,
        site_username="testuser",
        site_password="testpass123",
        session_secret="test-secret",
        google_client_id=None,
        google_client_secret=None,
        allowed_email=None,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _make_run(featured: bool = False) -> str:
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "Showcase test question", 8, 4)
    db.mark_completed(run_id, "Some answer [1].\n\n## References\n1. Paper. Author. 2024. PUBMED. http://x")
    db.set_featured(run_id, featured)
    return run_id


def test_featured_run_is_visible_without_a_session():
    run_id = _make_run(featured=True)
    client = TestClient(app)
    response = client.get(f"/runs/{run_id}", follow_redirects=False)
    assert response.status_code == 200


def test_non_featured_run_redirects_to_login_without_a_session():
    run_id = _make_run(featured=False)
    client = TestClient(app)
    response = client.get(f"/runs/{run_id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_only_an_authenticated_user_can_toggle_featured():
    run_id = _make_run(featured=False)
    client = TestClient(app)
    response = client.post(f"/runs/{run_id}/feature", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert not db.get_run(run_id)["featured"]


def test_authenticated_user_can_toggle_featured():
    run_id = _make_run(featured=False)
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123"},
            follow_redirects=False,
        )
        response = client.post(f"/runs/{run_id}/feature", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/runs/{run_id}"
    assert db.get_run(run_id)["featured"]
