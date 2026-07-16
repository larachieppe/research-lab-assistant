from src.state import Paper
from src.tools.evidence_graph import build_evidence_graph


def _paper(id_: str) -> Paper:
    return Paper(
        id=id_,
        source="pubmed",
        title=f"Title {id_}",
        authors=[],
        year=2024,
        abstract="",
        url=f"http://x/{id_}",
    )


def test_builds_one_node_per_cited_paper():
    papers = [_paper("a"), _paper("b"), _paper("c")]
    citation_number = {"a": 1, "b": 2, "c": 3}
    body = "Some claim [1]. Another claim [2].\n\nA third point [3]."
    graph = build_evidence_graph(body, papers, citation_number)
    assert {n.citation_number for n in graph.nodes} == {1, 2, 3}
    assert {n.paper_id for n in graph.nodes} == {"a", "b", "c"}


def test_edge_connects_papers_cited_in_the_same_paragraph():
    papers = [_paper("a"), _paper("b"), _paper("c")]
    citation_number = {"a": 1, "b": 2, "c": 3}
    body = "Papers 1 and 2 agree on this [1] [2].\n\nPaper 3 stands alone [3]."
    graph = build_evidence_graph(body, papers, citation_number)
    assert len(graph.edges) == 1
    edge = graph.edges[0]
    assert {edge.a, edge.b} == {1, 2}
    assert edge.weight == 1


def test_edge_weight_accumulates_across_multiple_paragraphs():
    papers = [_paper("a"), _paper("b")]
    citation_number = {"a": 1, "b": 2}
    body = "First point [1] [2].\n\nSecond point also [1] [2]."
    graph = build_evidence_graph(body, papers, citation_number)
    assert len(graph.edges) == 1
    assert graph.edges[0].weight == 2


def test_no_edges_when_no_paragraph_shares_two_citations():
    papers = [_paper("a"), _paper("b")]
    citation_number = {"a": 1, "b": 2}
    body = "Only paper one here [1].\n\nOnly paper two here [2]."
    graph = build_evidence_graph(body, papers, citation_number)
    assert graph.edges == []
