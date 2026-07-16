"""Filter agent: pre-screens candidate papers before the more expensive
per-paper extraction step.

A single batched call over full abstracts is still far cheaper than
running the full extractor on every retrieved paper, most of which are
only tangentially related - but sees the same abstract text the extractor
would, so its relevance judgment isn't handicapped by a truncated snippet.
"""

from __future__ import annotations

from src.llm import call_structured
from src.state import Paper

_SYSTEM = """You are screening candidate papers for relevance before a
research assistant extracts detailed findings from each one. You'll be
given a research question and a list of candidate papers with their full
abstracts.

Select a paper if its abstract gives direct, substantive evidence toward
answering the question - e.g. it reports a finding, comparison, mechanism,
or result that bears on it. If the question compares two things or has
multiple parts, a paper that directly addresses just ONE side or part is
still relevant evidence - do not require a single paper to cover the whole
compound question by itself; most won't. Do not select a paper just
because it shares a keyword or general subject area with the question with
no actual finding relevant to it, or is a general review with no specific
finding on this question. When several papers report very similar
evidence, prefer the ones with the most direct or specific findings over
near-duplicates."""

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


def filter_relevant_papers(question: str, papers: list[Paper]) -> list[str]:
    """Return the subset of paper ids worth running full extraction on."""
    if not papers:
        return []

    listing = "\n".join(
        f"[{p.id}] {p.title} ({p.year or 'n.d.'})\nAbstract: {p.abstract or '(no abstract available)'}"
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
