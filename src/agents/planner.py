"""Planner agent: turns a natural-language research question into search queries."""

from __future__ import annotations

from src.llm import call_structured

_SYSTEM = """You are a research librarian helping plan a literature search.
Given a research question, produce a short list of concise, keyword-style
search queries (not full sentences) suitable for searching PubMed and arXiv.
Cover different angles of the question (e.g. mechanism, application, a
specific technique or organism) rather than near-duplicate phrasings."""

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
