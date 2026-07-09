"""Filter agent: pre-screens candidate papers before the more expensive
per-paper extraction step.

A single batched call over titles + short abstract snippets is far cheaper
than running the full extractor (which sees the whole abstract) on every
retrieved paper, most of which are only tangentially related.
"""

from __future__ import annotations

from src.llm import call_structured
from src.state import Paper

_SYSTEM = """You are screening candidate papers for relevance before a
research assistant extracts detailed findings from each one. Given a
research question and a list of candidate papers (title + abstract
snippet), select only the papers likely to contain a claim or finding
directly relevant to the question. Exclude papers that are only
tangentially related, off-topic, or clearly redundant with a better match
already in the list."""

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant_paper_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The ids (exactly as given, e.g. 'pubmed:12345') of papers worth extracting detailed findings from.",
        }
    },
    "required": ["relevant_paper_ids"],
}

_ABSTRACT_SNIPPET_CHARS = 300


def filter_relevant_papers(question: str, papers: list[Paper]) -> list[str]:
    """Return the subset of paper ids worth running full extraction on."""
    if not papers:
        return []

    listing = "\n".join(
        f"[{p.id}] {p.title} ({p.year or 'n.d.'})\n"
        f"Abstract: {p.abstract[:_ABSTRACT_SNIPPET_CHARS] or '(no abstract available)'}"
        for p in papers
    )

    result = call_structured(
        system=_SYSTEM,
        user=f"Research question: {question}\n\nCandidate papers:\n{listing}",
        tool_name="submit_relevant_papers",
        tool_description="Submit the ids of papers worth extracting findings from.",
        input_schema=_INPUT_SCHEMA,
        max_tokens=1024,
    )

    known_ids = {p.id for p in papers}
    return [pid for pid in result.get("relevant_paper_ids", []) if pid in known_ids]
