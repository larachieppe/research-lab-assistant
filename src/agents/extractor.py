"""Extractor agent: pulls findings relevant to the research question out of one paper."""

from __future__ import annotations

from src.llm import call_structured
from src.state import Finding, Paper

_SYSTEM = """You are a meticulous research assistant extracting findings from a
paper abstract. Only extract claims that are directly relevant to the given
research question and are actually supported by the abstract text - never
speculate or add outside knowledge. If the abstract isn't relevant, say so."""

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {
            "type": "boolean",
            "description": "Whether this paper is relevant to the research question.",
        },
        "claims": {
            "type": "array",
            "items": {"type": "string"},
            "description": "1-3 concise findings/claims from the abstract relevant to the question. Empty if not relevant.",
        },
    },
    "required": ["relevant", "claims"],
}


def extract_findings(question: str, paper: Paper) -> Finding:
    if not paper.abstract:
        return Finding(paper_id=paper.id, claims=[])

    result = call_structured(
        system=_SYSTEM,
        user=(
            f"Research question: {question}\n\n"
            f"Paper title: {paper.title}\n"
            f"Abstract: {paper.abstract}"
        ),
        tool_name="submit_findings",
        tool_description="Submit the extracted findings for this paper.",
        input_schema=_INPUT_SCHEMA,
        max_tokens=512,
    )
    if not result.get("relevant", False):
        return Finding(paper_id=paper.id, claims=[])
    return Finding(paper_id=paper.id, claims=[c.strip() for c in result.get("claims", []) if c.strip()])
