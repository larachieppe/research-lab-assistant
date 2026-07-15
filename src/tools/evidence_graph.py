"""Builds the "evidence map": a graph connecting papers that are cited
together within the same paragraph of the generated answer.

Deliberately not a bibliometric citation graph (who-cites-whom) - the
retrieved papers come from independent keyword searches, not a citation
chain, so real citation links between them would usually be sparse or
empty. Co-citation within the synthesis is always populated and reflects
how the answer actually uses the evidence.
"""

from __future__ import annotations

import math
import re
from itertools import combinations

from src.state import EvidenceEdge, EvidenceGraph, EvidenceNode, Paper

_CITATION_RE = re.compile(r"\[(\d+)\]")

# SVG viewBox is 0 0 300 300; nodes sit on a circle centered in it.
_CENTER = 150.0
_RADIUS = 110.0


def _layout(n: int) -> list[tuple[float, float]]:
    if n <= 1:
        return [(_CENTER, _CENTER)] if n == 1 else []
    positions = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        positions.append((_CENTER + _RADIUS * math.cos(angle), _CENTER + _RADIUS * math.sin(angle)))
    return positions


def build_evidence_graph(
    body: str, cited_papers: list[Paper], citation_number: dict[str, int]
) -> EvidenceGraph:
    paragraphs = [p for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]

    edge_weights: dict[tuple[int, int], int] = {}
    for paragraph in paragraphs:
        numbers = sorted({int(n) for n in _CITATION_RE.findall(paragraph)})
        for a, b in combinations(numbers, 2):
            edge_weights[(a, b)] = edge_weights.get((a, b), 0) + 1

    positions = _layout(len(cited_papers))
    nodes = [
        EvidenceNode(
            citation_number=citation_number[paper.id],
            paper_id=paper.id,
            title=paper.title,
            year=paper.year,
            source=paper.source,
            url=paper.url,
            x=x,
            y=y,
        )
        for paper, (x, y) in zip(cited_papers, positions)
    ]
    edges = [EvidenceEdge(a=a, b=b, weight=weight) for (a, b), weight in edge_weights.items()]

    return EvidenceGraph(nodes=nodes, edges=edges)
