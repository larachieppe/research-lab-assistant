from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


@dataclass
class Paper:
    id: str  # e.g. "pubmed:38912345" or "arxiv:2401.01234"
    source: str  # "pubmed" | "arxiv"
    title: str
    authors: list[str]
    year: int | None
    abstract: str
    url: str


@dataclass
class Finding:
    paper_id: str
    claims: list[str] = field(default_factory=list)


class AgentState(TypedDict, total=False):
    question: str
    max_papers: int
    max_queries: int
    search_queries: list[str]
    papers: list[Paper]
    findings: list[Finding]
    summary: str
