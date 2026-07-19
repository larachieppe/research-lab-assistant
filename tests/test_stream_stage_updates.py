"""LangGraph represents a node that returns {} (e.g. filter_node's fail-open
path, hit whenever screening errors or flags zero papers as relevant) as
None in stream_mode="updates", not {} - so a naive result.update(node_output)
crashes with TypeError on exactly the runs this pipeline is designed to
survive. Reproduces both fail-open triggers end-to-end through the real
compiled graph (LLM/search calls mocked) and confirms the run completes
with a real answer instead of being marked failed.
"""

from unittest.mock import patch

from src.graph import build_graph
from src.state import Finding, Paper
from web.app import _stream_with_stage_updates

_STAGE_AFTER = {
    "planner": lambda r: "Searching PubMed and arXiv",
    "search": lambda r: f"Screening {len(r.get('papers', []))} papers for relevance",
    "filter": lambda r: f"Extracting evidence from {len(r.get('papers', []))} papers",
    "extract": lambda r: "Synthesizing answer",
}

_FAKE_PAPERS = [
    Paper(
        id="pubmed:1",
        source="pubmed",
        title="Paper A",
        authors=["X"],
        year=2022,
        abstract="a",
        url="http://x/1",
    )
]


def _run_with_mocked_filter(**filter_kwargs) -> dict:
    with (
        patch("src.graph.generate_search_queries", return_value=["query one"]),
        patch("src.graph.search_pubmed", return_value=_FAKE_PAPERS),
        patch("src.graph.search_arxiv", return_value=[]),
        patch(
            "src.graph.extract_findings",
            side_effect=lambda q, p: Finding(paper_id=p.id, claims=["a claim"]),
        ),
        patch("src.agents.synthesizer.call_text", return_value="Body text [1]."),
        patch("src.graph.filter_relevant_papers", **filter_kwargs),
    ):
        graph = build_graph()
        return _stream_with_stage_updates(
            "fake-run-id",
            graph,
            {"question": "test question", "max_papers": 12, "max_queries": 5},
            _STAGE_AFTER,
        )


def test_survives_filter_node_raising():
    result = _run_with_mocked_filter(side_effect=RuntimeError("simulated screening failure"))
    assert "Body text [1]" in result["summary"]


def test_survives_filter_node_flagging_zero_relevant():
    result = _run_with_mocked_filter(return_value=[])
    assert "Body text [1]" in result["summary"]
