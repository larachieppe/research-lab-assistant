from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.config import Settings
from web import ratelimit
from web.app import app
from web.ratelimit import rate_limit


class _FakeClient:
    host = "1.2.3.4"


class _FakeRequest:
    client = _FakeClient()


def test_rate_limit_dependency_allows_up_to_the_limit_then_blocks():
    dep = rate_limit(3, 60, "unit-test-bucket")
    for _ in range(3):
        dep(_FakeRequest())  # should not raise
    with pytest.raises(HTTPException) as exc_info:
        dep(_FakeRequest())
    assert exc_info.value.status_code == 429


def test_rate_limit_buckets_are_independent():
    dep_a = rate_limit(1, 60, "bucket-a")
    dep_b = rate_limit(1, 60, "bucket-b")
    dep_a(_FakeRequest())
    dep_b(_FakeRequest())  # different bucket, should not raise despite same IP


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


def test_login_route_is_rate_limited_after_ten_attempts():
    ratelimit._hits.clear()
    with patch("web.auth.load_settings", return_value=_settings()):
        client = TestClient(app)
        for _ in range(10):
            response = client.post(
                "/login", data={"username": "testuser", "password": "wrong"}, follow_redirects=False
            )
            assert response.status_code == 303

        eleventh = client.post(
            "/login", data={"username": "testuser", "password": "wrong"}, follow_redirects=False
        )
    assert eleventh.status_code == 429
