"""FastAPI web app wrapping the existing LangGraph pipeline (src/graph.py).

Every route requires a logged-in session (see web/auth.py) - it's meant to
be deployed publicly, and every run costs real Anthropic API calls, so
nothing here is reachable without logging in at /login first.
"""

from __future__ import annotations

import json
import re
import secrets
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

import markdown as md
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config import load_settings
from src.graph import build_graph
from web import auth, db
from web.auth import NotAuthenticated, require_auth
from web.templating import templates

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")

WEB_DIR = Path(__file__).resolve().parent

_settings = load_settings()
_session_secret = _settings.session_secret
if not _session_secret:
    # Fall back to a secret generated fresh at process start rather than
    # crashing the whole deploy over a missing env var - the only cost is
    # that everyone gets logged out whenever the process restarts, which
    # is a minor inconvenience, not a broken site.
    print(
        "WARNING: SESSION_SECRET is not set - generating a temporary one for "
        "this process. Sessions won't survive a restart until you set "
        "SESSION_SECRET (see .env.example).",
        file=sys.stderr,
    )
    _session_secret = secrets.token_hex(32)

app = FastAPI(title="Research Lab Assistant")
app.add_middleware(SessionMiddleware, secret_key=_session_secret, same_site="lax")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.include_router(auth.router)


@app.exception_handler(NotAuthenticated)
def handle_not_authenticated(request: Request, exc: NotAuthenticated) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


def _run_pipeline(run_id: str, question: str, max_papers: int, max_queries: int) -> None:
    db.mark_running(run_id)
    try:
        graph = build_graph()
        result = graph.invoke(
            {"question": question, "max_papers": max_papers, "max_queries": max_queries}
        )
        evidence_graph = result.get("evidence_graph")
        graph_json = json.dumps(asdict(evidence_graph)) if evidence_graph else None
        db.mark_completed(
            run_id,
            result.get("summary", ""),
            graph_json,
            result.get("excluded_retracted_count", 0),
        )
    except Exception as exc:
        db.mark_failed(run_id, str(exc))


def _wrap_citation_markers(html: str) -> str:
    return _CITATION_MARKER_RE.sub(
        lambda m: f'<span class="cite-marker" data-cite="{m.group(1)}">[{m.group(1)}]</span>',
        html,
    )


def _render_run(run: dict) -> dict:
    data = dict(run)
    summary = run["summary"] or ""
    body, _, references = summary.partition("## References")

    data["body_html"] = _wrap_citation_markers(md.markdown(body.strip())) if body.strip() else None
    data["references_html"] = md.markdown(references.strip()) if references.strip() else None
    data["graph"] = json.loads(run["evidence_graph_json"]) if run["evidence_graph_json"] else None
    return data


def _render_result_fragment(run: dict) -> str:
    return templates.env.get_template("_result.html").render(run=_render_run(run))


@app.get("/", dependencies=[Depends(require_auth)])
def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "recent_runs": db.list_runs(limit=5)}
    )


@app.post("/runs", dependencies=[Depends(require_auth)])
def submit_run(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    max_papers: int = Form(12),
    max_queries: int = Form(5),
):
    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    run_id = str(uuid.uuid4())
    db.create_run(run_id, question, max_papers, max_queries)
    background_tasks.add_task(_run_pipeline, run_id, question, max_papers, max_queries)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/runs/{run_id}", dependencies=[Depends(require_auth)])
def run_detail(request: Request, run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return templates.TemplateResponse(
        "run_detail.html", {"request": request, "run": _render_run(run)}
    )


@app.get("/api/runs/{run_id}", dependencies=[Depends(require_auth)])
def run_status(run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": run["status"], "html": _render_result_fragment(run)}


@app.get("/history", dependencies=[Depends(require_auth)])
def history(request: Request):
    return templates.TemplateResponse(
        "history.html", {"request": request, "runs": db.list_runs(limit=100)}
    )
