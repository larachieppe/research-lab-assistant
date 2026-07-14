from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import Settings
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


def test_protected_route_without_session_redirects_to_login():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_page_renders_without_google_button_when_unconfigured():
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        response = client.get("/login")
    assert response.status_code == 200
    assert "Sign in with Google" not in response.text
    assert "Log in" in response.text


def test_login_page_shows_google_button_when_configured():
    settings = _settings(google_client_id="client-id", google_client_secret="client-secret")
    with patch("web.auth.load_settings", return_value=settings):
        client = TestClient(app)
        response = client.get("/login")
    assert "Sign in with Google" in response.text


def test_correct_password_login_sets_session_and_grants_access():
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        login_response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123"},
            follow_redirects=False,
        )
        assert login_response.status_code == 303
        assert login_response.headers["location"] == "/"

        index_response = client.get("/", follow_redirects=False)
        assert index_response.status_code == 200


def test_wrong_password_login_redirects_with_error_and_grants_no_access():
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        login_response = client.post(
            "/login",
            data={"username": "testuser", "password": "wrong"},
            follow_redirects=False,
        )
        assert login_response.status_code == 303
        assert login_response.headers["location"] == "/login?error=invalid"

        index_response = client.get("/", follow_redirects=False)
        assert index_response.status_code == 303
        assert index_response.headers["location"] == "/login"


def test_logout_clears_session():
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123"},
            follow_redirects=False,
        )
        assert client.get("/", follow_redirects=False).status_code == 200

        client.get("/logout", follow_redirects=False)
        assert client.get("/", follow_redirects=False).status_code == 303
