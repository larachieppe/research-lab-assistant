from src.state import Paper
from src.tools.dedupe import dedupe_papers


def _paper(id_: str, title: str) -> Paper:
    return Paper(id=id_, source="pubmed", title=title, authors=[], year=2024, abstract="", url="")


def test_dedupe_drops_exact_title_repeats():
    papers = [_paper("a", "CRISPR gene editing"), _paper("b", "CRISPR gene editing")]
    assert len(dedupe_papers(papers)) == 1


def test_dedupe_ignores_case_and_punctuation():
    papers = [_paper("a", "Protein Folding: A Review!"), _paper("b", "protein folding a review")]
    assert len(dedupe_papers(papers)) == 1


def test_dedupe_keeps_distinct_titles():
    papers = [_paper("a", "Protein folding"), _paper("b", "Protein degradation")]
    assert len(dedupe_papers(papers)) == 2


def test_dedupe_preserves_first_occurrence_order():
    papers = [_paper("first", "Same Title"), _paper("second", "same title")]
    result = dedupe_papers(papers)
    assert len(result) == 1
    assert result[0].id == "first"
