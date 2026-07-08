from pathlib import Path

from src.tools.pubmed import parse_pubmed_xml

FIXTURE = Path(__file__).parent / "fixtures" / "pubmed_sample.xml"


def test_parses_all_articles_in_fixture():
    papers = parse_pubmed_xml(FIXTURE.read_bytes())
    assert len(papers) == 3


def test_parsed_paper_has_expected_fields():
    papers = parse_pubmed_xml(FIXTURE.read_bytes())
    paper = papers[0]
    assert paper.source == "pubmed"
    assert paper.id == "pubmed:42417804"
    assert paper.url == "https://pubmed.ncbi.nlm.nih.gov/42417804/"
    assert paper.title
    assert isinstance(paper.authors, list)


def test_handles_empty_result_set():
    empty_xml = b'<?xml version="1.0"?><PubmedArticleSet></PubmedArticleSet>'
    assert parse_pubmed_xml(empty_xml) == []
