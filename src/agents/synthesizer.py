"""Synthesizer agent: writes the final cited literature summary.

The reference list itself is built deterministically (not by the LLM) so
citation numbers always match what's in the body text - Claude only writes
the prose, using the citation numbers we hand it.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.llm import call_text
from src.state import EvidenceGraph, Finding, Paper, ReferenceEntry
from src.tools.evidence_graph import build_evidence_graph

_SYSTEM = """You are explaining research findings to a smart, curious reader
who is not a specialist in this field. Write a clear, plain-language answer
to the research question using only the evidence provided.

Avoid jargon. If a technical term is truly necessary, briefly explain what
it means in a few plain words the first time you use it. Prefer short,
direct sentences over dense academic phrasing - write to be understood, not
to sound scholarly.

Cite evidence inline with bracketed numbers like [1], [2] that EXACTLY match
the numbers given in the evidence list - do not renumber, invent, or omit
citations. When two or more papers support the same point, cite them
together in that sentence (e.g. "...off-target rates rise with mismatch
count [1][2]." rather than splitting them across separate sentences) - it
makes it clear which evidence agrees. Do not include a references section
yourself; just the body text.

When the evidence actually disagrees - different effect sizes, opposite
conclusions, or findings that only hold for a different population or
setting - say so explicitly rather than blending it into one confident-
sounding answer (e.g. "One study found X [1], while another found no such
effect [2], possibly because it looked at Y instead."). Only point out
disagreement that is really there in the evidence; don't manufacture
tension between findings that are simply about different aspects of the
question."""


@dataclass
class Synthesis:
    markdown: str
    graph: EvidenceGraph | None
    references: list[ReferenceEntry]


def _source_label(paper: Paper) -> str:
    if paper.source == "arxiv":
        return "ARXIV — Preprint (not peer-reviewed)"
    if paper.publication_types:
        return f"PUBMED — {', '.join(paper.publication_types)}"
    return "PUBMED"


def synthesize_summary(
    question: str,
    papers: list[Paper],
    findings: list[Finding],
    previous_question: str | None = None,
    previous_summary: str | None = None,
) -> Synthesis:
    findings_by_paper = {f.paper_id: f for f in findings}
    cited_papers = [p for p in papers if findings_by_paper.get(p.id) and findings_by_paper[p.id].claims]

    if not cited_papers:
        markdown = (
            f"No relevant findings were extracted from the retrieved papers for: "
            f'"{question}"\n\nTry rephrasing the question or increasing --max-papers.'
        )
        return Synthesis(markdown=markdown, graph=None, references=[])

    citation_number = {p.id: i + 1 for i, p in enumerate(cited_papers)}

    evidence_block = "\n".join(
        f"[{citation_number[p.id]}] {p.title} "
        f"({', '.join(p.authors[:3]) or 'Unknown authors'}, {p.year or 'n.d.'}): "
        f"{'; '.join(findings_by_paper[p.id].claims)}"
        for p in cited_papers
    )

    followup_context = (
        f"This is a follow-up to an earlier question in the same conversation - "
        f'the earlier question was: "{previous_question}"\n\n'
        f"The earlier answer was:\n{previous_summary}\n\n"
        "Write the new answer as a natural continuation: build on the earlier "
        "answer where relevant instead of repeating it, but don't assume the "
        "reader has it in front of them.\n\n"
        if previous_question and previous_summary
        else ""
    )

    body = call_text(
        system=_SYSTEM,
        user=(
            f"{followup_context}"
            f"Research question: {question}\n\n"
            f"Evidence extracted from papers:\n{evidence_block}\n\n"
            "Write a clear, plain-language answer (2-4 short paragraphs) to the "
            "research question, citing evidence inline with [n] matching the "
            "numbers above."
        ),
        max_tokens=1500,
    )
    body = body.strip()

    references = "\n".join(
        f"{citation_number[p.id]}. {p.title}. {', '.join(p.authors) or 'Unknown authors'}. "
        f"{p.year or 'n.d.'}. {_source_label(p)}. {p.url}"
        for p in cited_papers
    )

    markdown = f"{body}\n\n## References\n{references}\n"
    graph = build_evidence_graph(body, cited_papers, citation_number) if len(cited_papers) >= 2 else None

    reference_entries = [
        ReferenceEntry(
            number=citation_number[p.id],
            title=p.title,
            authors=p.authors,
            year=p.year,
            source=p.source,
            publication_types=p.publication_types,
            url=p.url,
        )
        for p in cited_papers
    ]

    return Synthesis(markdown=markdown, graph=graph, references=reference_entries)
