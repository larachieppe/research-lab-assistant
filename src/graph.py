"""Wires the five agents into a linear LangGraph pipeline:

    START -> planner -> search -> filter -> extract -> synthesize -> END

Search and extraction fan out across queries/papers with a thread pool -
each is many independent I/O-bound calls (HTTP to PubMed/arXiv, or to
Claude), so plain concurrency is simpler than LangGraph's Send API here and
keeps the graph itself easy to read.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langgraph.graph import END, START, StateGraph

from src.agents.extractor import extract_findings
from src.agents.filter import filter_relevant_papers
from src.agents.planner import generate_search_queries
from src.agents.synthesizer import synthesize_summary
from src.config import load_settings
from src.state import AgentState, Finding, Paper
from src.tools.arxiv import search_arxiv
from src.tools.dedupe import dedupe_papers
from src.tools.pubmed import search_pubmed
from src.tools.retraction import exclude_retracted


def planner_node(state: AgentState) -> dict:
    settings = load_settings()
    max_queries = state.get("max_queries", settings.max_search_queries)
    queries = generate_search_queries(state["question"], max_queries=max_queries)
    return {"search_queries": queries}


def search_node(state: AgentState) -> dict:
    settings = load_settings()
    queries = state["search_queries"]
    max_papers = state.get("max_papers", settings.max_papers)
    per_query_limit = max(3, max_papers // max(len(queries), 1))

    all_papers: list[Paper] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for query in queries:
            futures.append(executor.submit(search_pubmed, query, per_query_limit))
            futures.append(executor.submit(search_arxiv, query, per_query_limit))
        for future in futures:
            try:
                all_papers.extend(future.result())
            except Exception:
                # Tolerate a single source/query failing (rate limit, timeout, etc.)
                # rather than aborting the whole pipeline over one bad call.
                continue

    deduped = dedupe_papers(all_papers)
    kept, excluded_retracted_count = exclude_retracted(deduped)
    trimmed = kept[:max_papers]
    return {
        "papers": trimmed,
        # Preserved separately from "papers" so a later follow-up question can
        # re-filter against the full retrieved pool, not just whatever this
        # question's filter step narrowed "papers" down to.
        "candidate_papers": trimmed,
        "excluded_retracted_count": excluded_retracted_count,
    }


def filter_node(state: AgentState) -> dict:
    papers = state["papers"]
    try:
        relevant_ids = filter_relevant_papers(state["question"], papers)
    except Exception:
        # Fail open: if screening itself breaks, run extraction on everything
        # rather than silently dropping all candidates.
        return {}

    if not relevant_ids:
        # A screening call that flags *zero* of several candidates as
        # relevant is more likely a model/prompt hiccup than ground truth -
        # fail open here too rather than guaranteeing an empty synthesis.
        return {}

    id_set = set(relevant_ids)
    return {"papers": [p for p in papers if p.id in id_set]}


def extract_node(state: AgentState) -> dict:
    question = state["question"]
    papers = state["papers"]

    findings: list[Finding] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_paper = {executor.submit(extract_findings, question, paper): paper for paper in papers}
        for future in as_completed(future_to_paper):
            paper = future_to_paper[future]
            try:
                findings.append(future.result())
            except Exception:
                findings.append(Finding(paper_id=paper.id, claims=[]))

    return {"findings": findings}


def synthesize_node(state: AgentState) -> dict:
    synthesis = synthesize_summary(state["question"], state["papers"], state["findings"])
    return {"summary": synthesis.markdown, "evidence_graph": synthesis.graph}


def synthesize_followup_node(state: AgentState) -> dict:
    synthesis = synthesize_summary(
        state["question"],
        state["papers"],
        state["findings"],
        previous_question=state.get("previous_question"),
        previous_summary=state.get("previous_summary"),
    )
    return {"summary": synthesis.markdown, "evidence_graph": synthesis.graph}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("filter", filter_node)
    graph.add_node("extract", extract_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "filter")
    graph.add_edge("filter", "extract")
    graph.add_edge("extract", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


def build_followup_graph():
    """A cheaper pipeline for follow-up questions: reuses the parent run's
    already-retrieved paper pool (passed in as "papers") instead of planning
    and searching again.

        START -> filter -> extract -> synthesize -> END
    """
    graph = StateGraph(AgentState)
    graph.add_node("filter", filter_node)
    graph.add_node("extract", extract_node)
    graph.add_node("synthesize", synthesize_followup_node)

    graph.add_edge(START, "filter")
    graph.add_edge("filter", "extract")
    graph.add_edge("extract", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()
