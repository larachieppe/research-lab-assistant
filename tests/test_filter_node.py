from unittest.mock import patch

from src.graph import filter_node
from src.state import Paper


def _paper(id_: str) -> Paper:
    return Paper(
        id=id_, source="pubmed", title=f"Title {id_}", authors=[], year=2024, abstract="abstract", url=""
    )


def test_narrows_papers_to_the_relevant_subset():
    papers = [_paper("a"), _paper("b")]
    with patch("src.graph.filter_relevant_papers", return_value=["a"]):
        result = filter_node({"question": "q", "papers": papers})
    assert [p.id for p in result["papers"]] == ["a"]


def test_fails_open_when_nothing_is_flagged_relevant():
    papers = [_paper("a"), _paper("b")]
    with patch("src.graph.filter_relevant_papers", return_value=[]):
        result = filter_node({"question": "q", "papers": papers})
    assert result == {}


def test_fails_open_when_screening_call_raises():
    papers = [_paper("a"), _paper("b")]
    with patch("src.graph.filter_relevant_papers", side_effect=RuntimeError("boom")):
        result = filter_node({"question": "q", "papers": papers})
    assert result == {}
