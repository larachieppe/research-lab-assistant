"""arXiv API client: search papers via the public Atom feed at export.arxiv.org.

Parsing is split into a pure function so it can be unit-tested against a saved
fixture without hitting the network.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import requests
from tenacity import retry, stop_after_attempt, wait_random_exponential

from src.state import Paper

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _arxiv_id_from_entry_id(entry_id: str) -> str:
    # entry_id looks like "http://arxiv.org/abs/2401.01234v2"
    match = re.search(r"abs/([^v]+)", entry_id)
    return match.group(1) if match else entry_id


def parse_arxiv_atom(xml_bytes: bytes) -> list[Paper]:
    root = ET.fromstring(xml_bytes)
    papers: list[Paper] = []
    for entry in root.findall(f"{ATOM_NS}entry"):
        entry_id = entry.findtext(f"{ATOM_NS}id") or ""
        if not entry_id:
            continue
        arxiv_id = _arxiv_id_from_entry_id(entry_id)

        title = (entry.findtext(f"{ATOM_NS}title") or "(no title)").strip()
        title = re.sub(r"\s+", " ", title)

        abstract = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
        abstract = re.sub(r"\s+", " ", abstract)

        authors = [
            name.text.strip()
            for author in entry.findall(f"{ATOM_NS}author")
            if (name := author.find(f"{ATOM_NS}name")) is not None and name.text
        ]

        published = entry.findtext(f"{ATOM_NS}published") or ""
        year = int(published[:4]) if published[:4].isdigit() else None

        papers.append(
            Paper(
                id=f"arxiv:{arxiv_id}",
                source="arxiv",
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                url=f"https://arxiv.org/abs/{arxiv_id}",
            )
        )
    return papers


@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3))
def search_arxiv(query: str, max_results: int = 5) -> list[Paper]:
    params = {
        "search_query": f"all:{query}",
        "start": "0",
        "max_results": str(max_results),
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    resp = requests.get(ARXIV_API_URL, params=params, timeout=15)
    resp.raise_for_status()
    return parse_arxiv_atom(resp.content)
