"""FastAPI web app wrapping the existing LangGraph pipeline (src/graph.py).

The whole app sits behind HTTP Basic Auth - it's meant to be deployed
publicly, and every run costs real Anthropic API calls, so nothing here is
reachable without SITE_USERNAME/SITE_PASSWORD.
"""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path

import markdown as md
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import load_settings
from src.graph import build_graph
from web import db

WEB_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Research Lab Assistant")
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
templates = Jinja2Templates(directory=WEB_DIR / "templates")

security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    settings = load_settings()
    if not settings.site_username or not settings.site_password:
        raise HTTPException(
            status_code=500,
            detail="SITE_USERNAME/SITE_PASSWORD are not configured on the server.",
        )
    valid_username = secrets.compare_digest(credentials.username, settings.site_username)
    valid_password = secrets.compare_digest(credentials.password, settings.site_password)
    if not (valid_username and valid_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


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
        db.mark_completed(run_id, result.get("summary", ""))
    except Exception as exc:
        db.mark_failed(run_id, str(exc))


def _render_run(run: dict) -> dict:
    data = dict(run)
    data["summary_html"] = md.markdown(run["summary"]) if run["summary"] else None
    return data


@app.get("/", dependencies=[Depends(require_auth)])
def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "recent_runs": db.list_runs(limit=5)}
    )


@app.post("/runs", dependencies=[Depends(require_auth)])
def submit_run(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    max_papers: int = Form(8),
    max_queries: int = Form(4),
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
    rendered = _render_run(run)
    return {
        "status": rendered["status"],
        "summary_html": rendered["summary_html"],
        "error": rendered["error"],
    }


@app.get("/history", dependencies=[Depends(require_auth)])
def history(request: Request):
    return templates.TemplateResponse(
        "history.html", {"request": request, "runs": db.list_runs(limit=100)}
    )
