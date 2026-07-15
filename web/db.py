"""SQLite-backed storage for web app run history.

Separate from the CLI's outputs/*.md files - this only tracks runs
triggered through the web app, keyed by a uuid. Each helper opens and
closes its own short-lived connection, since sqlite3 connections aren't
safe to share across the threads FastAPI's BackgroundTasks run on.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DB_PATH = Path(os.environ.get("RUNS_DB_PATH", Path(__file__).resolve().parent.parent / "runs.db"))


@contextmanager
def _get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                max_papers INTEGER NOT NULL,
                max_queries INTEGER NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(runs)")}
        if "evidence_graph_json" not in existing_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN evidence_graph_json TEXT")
        if "excluded_retracted_count" not in existing_columns:
            conn.execute("ALTER TABLE runs ADD COLUMN excluded_retracted_count INTEGER")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(run_id: str, question: str, max_papers: int, max_queries: int) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, question, max_papers, max_queries, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (run_id, question, max_papers, max_queries, _now()),
        )


def mark_running(run_id: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))


def mark_completed(
    run_id: str,
    summary: str,
    evidence_graph_json: str | None = None,
    excluded_retracted_count: int = 0,
) -> None:
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE runs
            SET status = 'completed', summary = ?, evidence_graph_json = ?,
                excluded_retracted_count = ?, completed_at = ?
            WHERE id = ?
            """,
            (summary, evidence_graph_json, excluded_retracted_count, _now(), run_id),
        )


def mark_failed(run_id: str, error: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "UPDATE runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
            (error, _now(), run_id),
        )


def get_run(run_id: str) -> sqlite3.Row | None:
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()


def list_runs(limit: int = 50) -> list[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
