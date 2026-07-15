"""Builds the "evidence map": a graph connecting papers that are cited
together within the same paragraph of the generated answer.

Deliberately not a bibliometric citation graph (who-cites-whom) - the
retrieved papers come from independent keyword searches, not a citation
chain, so real citation links between them would usually be sparse or
empty. Co-citation within the synthesis is always populated and reflects
how the answer actually uses the evidence.

This only describes graph structure (nodes/edges) - layout is computed
client-side by a force simulation (web/static/evidence-map.js) so the
graph can react to dragging, which a server-computed layout can't.
"""

from __future__ import annotations

import re
from itertools import combinations

from src.state import EvidenceEdge, EvidenceGraph, EvidenceNode, Paper

_CITATION_RE = re.compile(r"\[(\d+)\]")


def build_evidence_graph(
    body: str, cited_papers: list[Paper], citation_number: dict[str, int]
) -> EvidenceGraph:
    paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]

    edge_weights: dict[tuple[int, int], int] = {}
    for paragraph in paragraphs:
        numbers = sorted({int(n) for n in _CITATION_RE.findall(paragraph)})
        for a, b in combinations(numbers, 2):
            edge_weights[(a, b)] = edge_weights.get((a, b), 0) + 1

    nodes = [
        EvidenceNode(
            citation_number=citation_number[paper.id],
            paper_id=paper.id,
            title=paper.title,
            year=paper.year,
            source=paper.source,
            url=paper.url,
        )
        for paper in cited_papers
    ]
    edges = [EvidenceEdge(a=a, b=b, weight=weight) for (a, b), weight in edge_weights.items()]

    return EvidenceGraph(nodes=nodes, edges=edges)
