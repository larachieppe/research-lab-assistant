"""LangGraph builds its state schema via typing.get_type_hints(AgentState) at
StateGraph construction time - this forces resolution of every annotation,
including ones only satisfied under TYPE_CHECKING. That gap let a real bug
(ReferenceEntry referenced in AgentState but never imported at runtime) slip
past every other test and reach production before being caught. These tests
just construct the graphs - no API key or network access needed - so that
class of bug fails locally and in CI instead.
"""

from src.graph import build_followup_graph, build_graph


def test_build_graph_constructs_without_error():
    build_graph()


def test_build_followup_graph_constructs_without_error():
    build_followup_graph()
