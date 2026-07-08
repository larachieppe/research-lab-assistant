"""Drop duplicate papers returned across different sources/queries.

PubMed and arXiv occasionally surface the same work (e.g. a preprint and its
published version), and the same query set can return overlapping results.
We dedupe on a normalized title rather than id, since ids are source-specific.
"""

from __future__ import annotations

import re

from src.state import Paper


def _normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    deduped: list[Paper] = []
    for paper in papers:
        key = _normalize_title(paper.title)
        if key and key not in seen:
            seen.add(key)
            deduped.append(paper)
    return deduped
