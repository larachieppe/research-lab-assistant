"""FastAPI web app wrapping the existing LangGraph pipeline (src/graph.py).

Every route requires a logged-in session (see web/auth.py) - it's meant to
be deployed publicly, and every run costs real Anthropic API calls, so
nothing here is reachable without logging in at /login first.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import uuid
from dataclasses import asdict
from pathlib import Path

import bleach
import markdown as md
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config import load_settings
from src.graph import build_followup_graph, build_graph
from src.state import Paper
from web import auth, db
from web.auth import NotAuthenticated, require_auth
from web.ratelimit import rate_limit
from web.templating import templates

_CITATION_MARKER_RE = re.compile(r"\[(\d+)\]")

# Allowlist for sanitizing the synthesizer's markdown->HTML output before
# it's ever marked "safe" in a template. Paper abstracts (untrusted, from
# PubMed/arXiv) flow into the LLM's context, and a prompt-injection payload
# hidden in one could get echoed back as raw HTML - markdown.markdown()
# passes raw HTML straight through by default, so this is the actual
# XSS boundary, not the templates.
_ALLOWED_TAGS = [
    "p",
    "br",
    "em",
    "strong",
    "ul",
    "ol",
    "li",
    "a",
    "span",
    "code",
    "pre",
    "blockquote",
    "h1",
    "h2",
    "h3",
    "hr",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "span": ["class", "data-cite"],
}

WEB_DIR = Path(__file__).resolve().parent
_ON_RENDER = os.environ.get("RENDER") == "true"

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
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    same_site="lax",
    https_only=_ON_RENDER,
    max_age=60 * 60 * 24 * 7,
)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
app.include_router(auth.router)
templates.env.globals["is_authenticated"] = auth.is_authenticated


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'"
    )
    if _ON_RENDER:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.exception_handler(NotAuthenticated)
def handle_not_authenticated(request: Request, exc: NotAuthenticated) -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=303)


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()


def _stream_with_stage_updates(run_id: str, graph, initial_state: dict, stage_after: dict) -> dict:
    """Run a compiled graph via .stream() instead of .invoke(), writing a
    human-readable "stage" to the DB as each node completes - stage_after
    maps a node name to a function(result_so_far) -> label describing the
    *next* step (e.g. once "search" finishes we know how many papers there
    are, so we can say "Screening N papers" for the upcoming filter step)."""
    result: dict = {}
    for update in graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_output in update.items():
            result.update(node_output)
            label = stage_after.get(node_name)
            if label:
                db.update_stage(run_id, label(result))
    return result


def _run_pipeline(run_id: str, question: str, max_papers: int, max_queries: int) -> None:
    db.mark_running(run_id)
    db.update_stage(run_id, "Planning search queries")
    try:
        graph = build_graph()
        result = _stream_with_stage_updates(
            run_id,
            graph,
            {"question": question, "max_papers": max_papers, "max_queries": max_queries},
            {
                "planner": lambda r: "Searching PubMed and arXiv",
                "search": lambda r: f"Screening {len(r.get('papers', []))} papers for relevance",
                "filter": lambda r: f"Extracting evidence from {len(r.get('papers', []))} papers",
                "extract": lambda r: "Synthesizing answer",
            },
        )
        evidence_graph = result.get("evidence_graph")
        graph_json = json.dumps(asdict(evidence_graph)) if evidence_graph else None
        candidate_papers = result.get("candidate_papers", [])
        papers_json = json.dumps([asdict(p) for p in candidate_papers]) if candidate_papers else None
        references = result.get("references", [])
        references_json = json.dumps([asdict(r) for r in references]) if references else None
        db.mark_completed(
            run_id,
            result.get("summary", ""),
            graph_json,
            result.get("excluded_retracted_count", 0),
            papers_json,
            references_json,
        )
    except Exception as exc:
        db.mark_failed(run_id, str(exc))


def _run_followup_pipeline(
    run_id: str,
    question: str,
    candidate_papers_json: str,
    previous_question: str,
    previous_summary: str,
) -> None:
    db.mark_running(run_id)
    try:
        candidate_papers = [Paper(**p) for p in json.loads(candidate_papers_json)]
        db.update_stage(run_id, f"Screening {len(candidate_papers)} papers for relevance")
        graph = build_followup_graph()
        result = _stream_with_stage_updates(
            run_id,
            graph,
            {
                "question": question,
                "papers": candidate_papers,
                "previous_question": previous_question,
                "previous_summary": previous_summary,
            },
            {
                "filter": lambda r: f"Extracting evidence from {len(r.get('papers', []))} papers",
                "extract": lambda r: "Synthesizing answer",
            },
        )
        evidence_graph = result.get("evidence_graph")
        graph_json = json.dumps(asdict(evidence_graph)) if evidence_graph else None
        references = result.get("references", [])
        references_json = json.dumps([asdict(r) for r in references]) if references else None
        # Always carry the full inherited pool forward, not whatever this
        # follow-up's own filter step narrowed "papers" down to - so a later
        # follow-up-to-this-follow-up still has the original full pool to draw from.
        db.mark_completed(
            run_id,
            result.get("summary", ""),
            graph_json,
            0,
            candidate_papers_json,
            references_json,
        )
    except Exception as exc:
        db.mark_failed(run_id, str(exc))


def _wrap_citation_markers(html: str) -> str:
    return _CITATION_MARKER_RE.sub(
        lambda m: f'<span class="cite-marker" data-cite="{m.group(1)}">[{m.group(1)}]</span>',
        html,
    )


def _sanitize(html: str) -> str:
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, strip=True)


def _render_run(run: dict) -> dict:
    data = dict(run)
    summary = run["summary"] or ""
    body, _, references = summary.partition("## References")

    data["body_html"] = _wrap_citation_markers(_sanitize(md.markdown(body.strip()))) if body.strip() else None
    # references_json (paper cards) is preferred; older runs predating this
    # column fall back to the markdown-parsed references block instead.
    data["references"] = json.loads(run["references_json"]) if run["references_json"] else None
    data["references_html"] = (
        _sanitize(md.markdown(references.strip())) if not data["references"] and references.strip() else None
    )
    data["graph"] = json.loads(run["evidence_graph_json"]) if run["evidence_graph_json"] else None
    return data


def _render_result_fragment(run: dict) -> str:
    return templates.env.get_template("_result.html").render(run=_render_run(run))


@app.get("/")
def showcase(request: Request):
    return templates.TemplateResponse(
        "showcase.html", {"request": request, "featured_runs": db.list_featured_runs()}
    )


@app.get("/ask", dependencies=[Depends(require_auth)])
def ask(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "recent_runs": db.list_runs(limit=5)}
    )


@app.post(
    "/runs",
    dependencies=[Depends(require_auth), Depends(rate_limit(20, 3600, "runs"))],
)
def submit_run(
    background_tasks: BackgroundTasks,
    question: str = Form(...),
    max_papers: int = Form(12),
    max_queries: int = Form(5),
):
    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    # The client-side <input min max> is not trustworthy on its own - a
    # crafted request could otherwise demand an arbitrarily large run and
    # burn through Anthropic/NCBI rate limits.
    max_papers = max(2, min(max_papers, 20))
    max_queries = max(1, min(max_queries, 6))

    run_id = str(uuid.uuid4())
    db.create_run(run_id, question, max_papers, max_queries)
    background_tasks.add_task(_run_pipeline, run_id, question, max_papers, max_queries)
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


def _visible_or_redirect(request: Request, run: dict) -> RedirectResponse | None:
    """Featured runs are publicly viewable; everything else needs a session."""
    if run["featured"] or auth.is_authenticated(request):
        return None
    return RedirectResponse(url="/login", status_code=303)


@app.get("/runs/{run_id}")
def run_detail(request: Request, run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    redirect = _visible_or_redirect(request, run)
    if redirect is not None:
        return redirect
    parent = db.get_run(run["parent_run_id"]) if run["parent_run_id"] else None
    return templates.TemplateResponse(
        "run_detail.html",
        {
            "request": request,
            "run": _render_run(run),
            "parent": parent,
            "children": db.list_children(run_id),
        },
    )


@app.get("/api/runs/{run_id}")
def run_status(request: Request, run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    redirect = _visible_or_redirect(request, run)
    if redirect is not None:
        raise HTTPException(status_code=401, detail="Not authorized")
    return {"status": run["status"], "html": _render_result_fragment(run)}


@app.post(
    "/runs/{run_id}/followup",
    dependencies=[Depends(require_auth), Depends(rate_limit(20, 3600, "runs"))],
)
def submit_followup(
    background_tasks: BackgroundTasks,
    run_id: str,
    question: str = Form(...),
):
    parent = db.get_run(run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not parent["papers_json"]:
        raise HTTPException(
            status_code=400,
            detail="This run has no saved evidence pool to follow up on (it predates the follow-up feature).",
        )

    question = question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    new_run_id = str(uuid.uuid4())
    db.create_run(new_run_id, question, parent["max_papers"], parent["max_queries"], parent_run_id=run_id)
    background_tasks.add_task(
        _run_followup_pipeline,
        new_run_id,
        question,
        parent["papers_json"],
        parent["question"],
        parent["summary"] or "",
    )
    return RedirectResponse(url=f"/runs/{new_run_id}", status_code=303)


@app.post("/runs/{run_id}/feature", dependencies=[Depends(require_auth)])
def toggle_featured(run_id: str):
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    db.set_featured(run_id, not run["featured"])
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@app.get("/history", dependencies=[Depends(require_auth)])
def history(request: Request):
    return templates.TemplateResponse("history.html", {"request": request, "runs": db.list_runs(limit=100)})
