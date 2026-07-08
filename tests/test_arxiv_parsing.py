from pathlib import Path

from src.tools.arxiv import parse_arxiv_atom

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_sample.xml"


def test_parses_all_entries_in_fixture():
    papers = parse_arxiv_atom(FIXTURE.read_bytes())
    assert len(papers) == 3


def test_parsed_paper_has_expected_fields():
    papers = parse_arxiv_atom(FIXTURE.read_bytes())
    paper = papers[0]
    assert paper.source == "arxiv"
    assert paper.id == "arxiv:2410.08355"
    assert paper.url == "https://arxiv.org/abs/2410.08355"
    assert paper.year == 2024
    assert "Metalic" in paper.title
    assert paper.authors


def test_handles_empty_feed():
    empty_atom = (
        b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
    )
    assert parse_arxiv_atom(empty_atom) == []
