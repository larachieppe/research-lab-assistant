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
    # PubMed's own PublicationType values (e.g. "Journal Article", "Review",
    # "Randomized Controlled Trial", "Meta-Analysis", "Retracted Publication").
    # Always empty for arXiv preprints - they don't carry this metadata.
    publication_types: list[str] = field(default_factory=list)
    retracted: bool = False


@dataclass
class Finding:
    paper_id: str
    claims: list[str] = field(default_factory=list)


@dataclass
class EvidenceNode:
    citation_number: int
    paper_id: str
    title: str
    year: int | None
    source: str
    url: str


@dataclass
class EvidenceEdge:
    a: int  # citation numbers of the two co-cited papers
    b: int
    weight: int


@dataclass
class EvidenceGraph:
    nodes: list[EvidenceNode]
    edges: list[EvidenceEdge]


@dataclass
class ReferenceEntry:
    number: int
    title: str
    authors: list[str]
    year: int | None
    source: str
    publication_types: list[str]
    url: str


class AgentState(TypedDict, total=False):
    question: str
    max_papers: int
    max_queries: int
    search_queries: list[str]
    papers: list[Paper]
    candidate_papers: list[Paper]
    findings: list[Finding]
    summary: str
    evidence_graph: EvidenceGraph | None
    excluded_retracted_count: int
    previous_question: str
    previous_summary: str
    references: list[ReferenceEntry]
