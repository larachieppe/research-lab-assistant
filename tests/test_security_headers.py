from fastapi.testclient import TestClient

from web.app import app


def test_security_headers_present_on_every_response():
    client = TestClient(app)
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]


def test_hsts_not_set_outside_render():
    # _ON_RENDER is read once at import time from RENDER env var, which
    # isn't set in local/test runs - so HSTS shouldn't be sent here (it
    # would otherwise force HTTPS on local http://localhost dev too).
    client = TestClient(app)
    response = client.get("/")
    assert "strict-transport-security" not in response.headers
