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

Most questions describe a single relationship, mechanism, or finding (e.g.
"how does X affect Y", "does X influence Y"). For these, keep the key
terms of that relationship TOGETHER in each query (e.g. "X Y mechanism",
"X effect on Y") - do not split X and Y into separate single-concept
queries, since that loses the very relationship the question is asking
about and a query for just "Y" alone is usually too generic to be useful.

Only split into separate per-side queries when the question explicitly
contrasts two distinct, named alternatives using words like "compared to",
"versus", "vs.", or "or is it" - e.g. "does mRNA vaccine design affect T-cell
durability compared to protein subunit vaccines?" genuinely needs one query
anchored on the mRNA side and one anchored on the protein-subunit side,
since a single paper is unlikely to cover both platforms at once. Do not
apply this splitting to questions that simply mention two concepts without
an explicit contrast between them."""

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
