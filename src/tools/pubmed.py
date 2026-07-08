"""NCBI E-utilities client: search PubMed and fetch structured records.

Two calls per search: esearch (query -> PMIDs) then efetch (PMIDs -> XML records).
Parsing is split into a pure function so it can be unit-tested against a saved
fixture without hitting the network.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET

import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential

from src.config import load_settings
from src.state import Paper

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _polite_params() -> dict[str, str]:
    settings = load_settings()
    params: dict[str, str] = {}
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    return params


def _rate_limit_sleep() -> None:
    # NCBI allows 10 req/sec with an api key, 3 req/sec without.
    settings = load_settings()
    time.sleep(0.11 if settings.ncbi_api_key else 0.35)


def parse_pubmed_xml(xml_bytes: bytes) -> list[Paper]:
    root = ET.fromstring(xml_bytes)
    papers: list[Paper] = []
    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else None
        if not pmid:
            continue

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()).strip() if title_el is not None else "(no title)"

        abstract_parts = [
            "".join(node.itertext()) for node in article.findall(".//Abstract/AbstractText")
        ]
        abstract = " ".join(part.strip() for part in abstract_parts if part.strip())

        authors: list[str] = []
        for author_el in article.findall(".//AuthorList/Author"):
            last = author_el.findtext("LastName")
            fore = author_el.findtext("ForeName")
            if last and fore:
                authors.append(f"{fore} {last}")
            elif last:
                authors.append(last)

        year_text = (
            article.findtext(".//JournalIssue/PubDate/Year")
            or article.findtext(".//JournalIssue/PubDate/MedlineDate", default="")[:4]
        )
        year = int(year_text) if year_text and year_text.isdigit() else None

        papers.append(
            Paper(
                id=f"pubmed:{pmid}",
                source="pubmed",
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        )
    return papers


@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3))
def search_pubmed(query: str, max_results: int = 5) -> list[Paper]:
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
        "sort": "relevance",
        **_polite_params(),
    }
    resp = requests.get(ESEARCH_URL, params=search_params, timeout=15)
    resp.raise_for_status()
    ids = resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    _rate_limit_sleep()

    fetch_params = {
        "db": "pubmed",
        "id": ",".join(ids),
        "retmode": "xml",
        **_polite_params(),
    }
    resp = requests.get(EFETCH_URL, params=fetch_params, timeout=15)
    resp.raise_for_status()
    return parse_pubmed_xml(resp.content)
