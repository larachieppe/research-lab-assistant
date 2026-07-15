from src.state import Paper
from src.tools.retraction import exclude_retracted


def _paper(id_: str, retracted: bool = False) -> Paper:
    return Paper(
        id=id_, source="pubmed", title=f"Title {id_}", authors=[], year=2024, abstract="", url="",
        retracted=retracted,
    )


def test_keeps_non_retracted_papers():
    papers = [_paper("a"), _paper("b")]
    kept, excluded_count = exclude_retracted(papers)
    assert kept == papers
    assert excluded_count == 0


def test_drops_retracted_papers_and_counts_them():
    papers = [_paper("a"), _paper("b", retracted=True), _paper("c", retracted=True)]
    kept, excluded_count = exclude_retracted(papers)
    assert [p.id for p in kept] == ["a"]
    assert excluded_count == 2


def test_handles_empty_list():
    kept, excluded_count = exclude_retracted([])
    assert kept == []
    assert excluded_count == 0
