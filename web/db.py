"""Run history storage: local SQLite by default, or Postgres when
DATABASE_URL is set (e.g. a free Neon project).

SQLite alone doesn't survive Render's free tier: there's no persistent
disk, so the local file gets wiped on every redeploy and on free-tier
idle-restarts. DATABASE_URL absent means local SQLite, unchanged from
before - so local dev and the test suite need zero setup. Both backends
expose the same seven functions and always return plain dicts, so callers
(web/app.py) don't need to know or care which one is active.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

DATABASE_URL = os.environ.get("DATABASE_URL")


def _now() -> str:
    return datetime.now(UTC).isoformat()


if DATABASE_URL:
    import psycopg
    from psycopg.rows import dict_row

    def _get_conn():
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

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
                    completed_at TEXT,
                    evidence_graph_json TEXT,
                    excluded_retracted_count INTEGER,
                    featured BOOLEAN NOT NULL DEFAULT FALSE,
                    parent_run_id TEXT,
                    papers_json TEXT,
                    stage TEXT,
                    references_json TEXT
                )
                """
            )
            # Idempotent no-ops on a fresh table - only matter when
            # upgrading a pre-existing Postgres table from an older schema.
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS evidence_graph_json TEXT")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS excluded_retracted_count INTEGER")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS featured BOOLEAN NOT NULL DEFAULT FALSE")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS parent_run_id TEXT")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS papers_json TEXT")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS stage TEXT")
            conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS references_json TEXT")

    def create_run(
        run_id: str,
        question: str,
        max_papers: int,
        max_queries: int,
        parent_run_id: str | None = None,
    ) -> None:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, question, max_papers, max_queries, status, created_at, parent_run_id)
                VALUES (%s, %s, %s, %s, 'pending', %s, %s)
                """,
                (run_id, question, max_papers, max_queries, _now(), parent_run_id),
            )

    def mark_running(run_id: str) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET status = 'running' WHERE id = %s", (run_id,))

    def update_stage(run_id: str, stage: str) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET stage = %s WHERE id = %s", (stage, run_id))

    def mark_completed(
        run_id: str,
        summary: str,
        evidence_graph_json: str | None = None,
        excluded_retracted_count: int = 0,
        papers_json: str | None = None,
        references_json: str | None = None,
    ) -> None:
        with _get_conn() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'completed', summary = %s, evidence_graph_json = %s,
                    excluded_retracted_count = %s, papers_json = %s, references_json = %s,
                    completed_at = %s
                WHERE id = %s
                """,
                (
                    summary,
                    evidence_graph_json,
                    excluded_retracted_count,
                    papers_json,
                    references_json,
                    _now(),
                    run_id,
                ),
            )

    def mark_failed(run_id: str, error: str) -> None:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE runs SET status = 'failed', error = %s, completed_at = %s WHERE id = %s",
                (error, _now(), run_id),
            )

    def get_run(run_id: str) -> dict | None:
        with _get_conn() as conn:
            return conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()

    def list_runs(limit: int = 50) -> list[dict]:
        with _get_conn() as conn:
            return conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT %s", (limit,)).fetchall()

    def set_featured(run_id: str, featured: bool) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET featured = %s WHERE id = %s", (featured, run_id))

    def list_featured_runs(limit: int = 8) -> list[dict]:
        with _get_conn() as conn:
            return conn.execute(
                """
                SELECT * FROM runs WHERE featured = TRUE AND status = 'completed'
                ORDER BY created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()

    def list_children(parent_run_id: str) -> list[dict]:
        with _get_conn() as conn:
            return conn.execute(
                "SELECT * FROM runs WHERE parent_run_id = %s ORDER BY created_at ASC",
                (parent_run_id,),
            ).fetchall()

else:
    import sqlite3
    from collections.abc import Iterator
    from contextlib import contextmanager
    from pathlib import Path

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
            if "featured" not in existing_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN featured INTEGER NOT NULL DEFAULT 0")
            if "parent_run_id" not in existing_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN parent_run_id TEXT")
            if "papers_json" not in existing_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN papers_json TEXT")
            if "stage" not in existing_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN stage TEXT")
            if "references_json" not in existing_columns:
                conn.execute("ALTER TABLE runs ADD COLUMN references_json TEXT")

    def create_run(
        run_id: str,
        question: str,
        max_papers: int,
        max_queries: int,
        parent_run_id: str | None = None,
    ) -> None:
        with _get_conn() as conn:
            conn.execute(
                """
                INSERT INTO runs (id, question, max_papers, max_queries, status, created_at, parent_run_id)
                VALUES (?, ?, ?, ?, 'pending', ?, ?)
                """,
                (run_id, question, max_papers, max_queries, _now(), parent_run_id),
            )

    def mark_running(run_id: str) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET status = 'running' WHERE id = ?", (run_id,))

    def update_stage(run_id: str, stage: str) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET stage = ? WHERE id = ?", (stage, run_id))

    def mark_completed(
        run_id: str,
        summary: str,
        evidence_graph_json: str | None = None,
        excluded_retracted_count: int = 0,
        papers_json: str | None = None,
        references_json: str | None = None,
    ) -> None:
        with _get_conn() as conn:
            conn.execute(
                """
                UPDATE runs
                SET status = 'completed', summary = ?, evidence_graph_json = ?,
                    excluded_retracted_count = ?, papers_json = ?, references_json = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    summary,
                    evidence_graph_json,
                    excluded_retracted_count,
                    papers_json,
                    references_json,
                    _now(),
                    run_id,
                ),
            )

    def mark_failed(run_id: str, error: str) -> None:
        with _get_conn() as conn:
            conn.execute(
                "UPDATE runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
                (error, _now(), run_id),
            )

    def get_run(run_id: str) -> dict | None:
        with _get_conn() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            return dict(row) if row is not None else None

    def list_runs(limit: int = 50) -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            return [dict(row) for row in rows]

    def set_featured(run_id: str, featured: bool) -> None:
        with _get_conn() as conn:
            conn.execute("UPDATE runs SET featured = ? WHERE id = ?", (1 if featured else 0, run_id))

    def list_featured_runs(limit: int = 8) -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM runs WHERE featured = 1 AND status = 'completed'
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_children(parent_run_id: str) -> list[dict]:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE parent_run_id = ? ORDER BY created_at ASC",
                (parent_run_id,),
            ).fetchall()
            return [dict(row) for row in rows]
