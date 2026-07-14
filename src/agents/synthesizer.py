"""Synthesizer agent: writes the final cited literature summary.

The reference list itself is built deterministically (not by the LLM) so
citation numbers always match what's in the body text - Claude only writes
the prose, using the citation numbers we hand it.
"""

from __future__ import annotations

from src.llm import call_text
from src.state import Finding, Paper

_SYSTEM = """You are explaining research findings to a smart, curious reader
who is not a specialist in this field. Write a clear, plain-language answer
to the research question using only the evidence provided.

Avoid jargon. If a technical term is truly necessary, briefly explain what
it means in a few plain words the first time you use it. Prefer short,
direct sentences over dense academic phrasing - write to be understood, not
to sound scholarly.

Cite evidence inline with bracketed numbers like [1], [2] that EXACTLY match
the numbers given in the evidence list - do not renumber, invent, or omit
citations. Do not include a references section yourself; just the body text."""


def synthesize_summary(question: str, papers: list[Paper], findings: list[Finding]) -> str:
    findings_by_paper = {f.paper_id: f for f in findings}
    cited_papers = [p for p in papers if findings_by_paper.get(p.id) and findings_by_paper[p.id].claims]

    if not cited_papers:
        return (
            f"No relevant findings were extracted from the retrieved papers for: "
            f"\"{question}\"\n\nTry rephrasing the question or increasing --max-papers."
        )

    citation_number = {p.id: i + 1 for i, p in enumerate(cited_papers)}

    evidence_block = "\n".join(
        f"[{citation_number[p.id]}] {p.title} "
        f"({', '.join(p.authors[:3]) or 'Unknown authors'}, {p.year or 'n.d.'}): "
        f"{'; '.join(findings_by_paper[p.id].claims)}"
        for p in cited_papers
    )

    body = call_text(
        system=_SYSTEM,
        user=(
            f"Research question: {question}\n\n"
            f"Evidence extracted from papers:\n{evidence_block}\n\n"
            "Write a clear, plain-language answer (2-4 short paragraphs) to the "
            "research question, citing evidence inline with [n] matching the "
            "numbers above."
        ),
        max_tokens=1500,
    )

    references = "\n".join(
        f"{citation_number[p.id]}. {p.title}. {', '.join(p.authors) or 'Unknown authors'}. "
        f"{p.year or 'n.d.'}. {p.source.upper()}. {p.url}"
        for p in cited_papers
    )

    return f"{body.strip()}\n\n## References\n{references}\n"
