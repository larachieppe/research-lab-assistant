"""Planner agent: turns a natural-language research question into search queries."""

from __future__ import annotations

from src.llm import call_structured

_SYSTEM = """You are a research librarian helping plan a literature search
across PubMed and arXiv - which together cover far more than biology
(medicine, physics, CS, math, statistics, economics, engineering, etc.), so
plan queries appropriate to whatever field the question is actually in.

Produce a short list of concise, keyword-style search queries (2-6 words
each, not full sentences or boolean expressions - these engines match
literal terms, so long compound phrases tend to return few or no results).

If the question compares two things or has multiple parts (e.g. "does A
affect B compared to C?"), do NOT just write one query for the whole
compound question - generate a separate query for each side/part on its own
(one anchored on A, one anchored on C, etc.) plus, if space remains, one
query for the direct comparison. Individual papers are far more likely to
address one side of a comparison than the whole thing at once, and each
side needs its own retrieval to be found at all."""

_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Keyword-style search queries covering distinct angles of the question.",
        }
    },
    "required": ["queries"],
}


def generate_search_queries(question: str, max_queries: int = 4) -> list[str]:
    result = call_structured(
        system=_SYSTEM,
        user=f"Research question: {question}\n\nGenerate up to {max_queries} search queries.",
        tool_name="submit_search_queries",
        tool_description="Submit the planned search queries.",
        input_schema=_INPUT_SCHEMA,
        max_tokens=512,
    )
    queries = [q.strip() for q in result.get("queries", []) if q.strip()]
    return queries[:max_queries] or [question]
