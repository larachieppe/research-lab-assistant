from unittest.mock import patch

from src.agents.filter import filter_relevant_papers
from src.state import Paper


def _paper(id_: str) -> Paper:
    return Paper(id=id_, source="pubmed", title=f"Title {id_}", authors=[], year=2024, abstract="abstract", url="")


def test_drops_hallucinated_ids_not_in_candidate_set():
    papers = [_paper("a"), _paper("b"), _paper("c")]
    with patch("src.agents.filter.call_structured") as mock_call:
        mock_call.return_value = {"relevant_paper_ids": ["a", "c", "made-up-id"]}
        result = filter_relevant_papers("some question", papers)
    assert result == ["a", "c"]


def test_returns_empty_list_when_model_flags_none_relevant():
    papers = [_paper("a")]
    with patch("src.agents.filter.call_structured") as mock_call:
        mock_call.return_value = {"relevant_paper_ids": []}
        result = filter_relevant_papers("some question", papers)
    assert result == []


def test_short_circuits_on_empty_paper_list_without_calling_llm():
    with patch("src.agents.filter.call_structured") as mock_call:
        result = filter_relevant_papers("some question", [])
    assert result == []
    mock_call.assert_not_called()
