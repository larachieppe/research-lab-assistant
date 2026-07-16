import json
import uuid
from dataclasses import asdict
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.config import Settings
from src.state import Paper
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


def _sample_papers_json() -> str:
    paper = Paper(
        id="pubmed:1",
        source="pubmed",
        title="A paper",
        authors=["Someone"],
        year=2024,
        abstract="An abstract.",
        url="http://x",
    )
    return json.dumps([asdict(paper)])


def _make_run(papers_json: str | None = "") -> str:
    run_id = str(uuid.uuid4())
    db.create_run(run_id, "Parent question", 8, 4)
    db.mark_completed(
        run_id,
        "Some answer [1].\n\n## References\n1. Paper. Author. 2024. PUBMED. http://x",
        papers_json=papers_json if papers_json != "" else _sample_papers_json(),
    )
    return run_id


def _logged_in_client() -> TestClient:
    client = TestClient(app)
    with patch("web.auth.load_settings", return_value=_settings()):
        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass123"},
            follow_redirects=False,
        )
    return client


def test_followup_without_a_session_redirects_to_login():
    run_id = _make_run()
    client = TestClient(app)
    response = client.post(f"/runs/{run_id}/followup", data={"question": "follow up?"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_followup_creates_a_child_run_with_parent_link():
    run_id = _make_run()
    client = _logged_in_client()
    response = client.post(f"/runs/{run_id}/followup", data={"question": "follow up?"}, follow_redirects=False)
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/runs/")
    child_id = location.removeprefix("/runs/")

    child = db.get_run(child_id)
    assert child["parent_run_id"] == run_id
    assert child["question"] == "follow up?"

    children = db.list_children(run_id)
    assert [c["id"] for c in children] == [child_id]


def test_followup_rejects_empty_question():
    run_id = _make_run()
    client = _logged_in_client()
    response = client.post(f"/runs/{run_id}/followup", data={"question": "   "}, follow_redirects=False)
    assert response.status_code == 400


def test_followup_on_run_without_papers_json_is_rejected():
    run_id = _make_run(papers_json=None)
    client = _logged_in_client()
    response = client.post(f"/runs/{run_id}/followup", data={"question": "follow up?"}, follow_redirects=False)
    assert response.status_code == 400


def test_followup_on_missing_run_is_404():
    client = _logged_in_client()
    response = client.post(f"/runs/{uuid.uuid4()}/followup", data={"question": "follow up?"}, follow_redirects=False)
    assert response.status_code == 404
