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


def test_extracts_publication_types_from_fixture():
    papers = parse_pubmed_xml(FIXTURE.read_bytes())
    assert papers[0].publication_types == ["Journal Article"]
    assert papers[0].retracted is False


def _article_xml(*, publication_types: list[str] = (), comments_corrections: str = "") -> bytes:
    pub_types = "".join(f"<PublicationType>{pt}</PublicationType>" for pt in publication_types)
    return f"""<?xml version="1.0"?>
    <PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>99999999</PMID>
          <Article>
            <ArticleTitle>A retracted study</ArticleTitle>
            <PublicationTypeList>{pub_types}</PublicationTypeList>
          </Article>
          {comments_corrections}
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>""".encode()


def test_detects_retraction_via_publication_type():
    xml = _article_xml(publication_types=["Journal Article", "Retracted Publication"])
    papers = parse_pubmed_xml(xml)
    assert papers[0].retracted is True


def test_detects_retraction_via_comments_corrections():
    xml = _article_xml(
        publication_types=["Journal Article"],
        comments_corrections=(
            '<CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn">'
            "</CommentsCorrections></CommentsCorrectionsList>"
        ),
    )
    papers = parse_pubmed_xml(xml)
    assert papers[0].retracted is True


def test_not_retracted_when_no_signal_present():
    xml = _article_xml(publication_types=["Journal Article", "Review"])
    papers = parse_pubmed_xml(xml)
    assert papers[0].retracted is False
    assert papers[0].publication_types == ["Journal Article", "Review"]
