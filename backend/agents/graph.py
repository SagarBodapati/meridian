"""
LangGraph workflow definition.

Graph topology:
  START → router → [simple_rag | multi_hop | comparative | report] → END

Each node mutates AgentState and returns it.
Streaming is handled at the API layer by calling agent.stream() directly.
"""
from typing import AsyncIterator, Literal

import structlog
from langgraph.graph import END, START, StateGraph

from backend.agents.comparative import ComparativeAgent
from backend.agents.multi_hop import MultiHopAgent
from backend.agents.router import QueryRouter
from backend.agents.simple_rag import SimpleRAGAgent
from backend.agents.state import AgentState
from backend.models.queries import QueryType

log = structlog.get_logger()


def _route_decision(state: AgentState) -> Literal["simple_rag", "multi_hop", "comparative", "report"]:
    qt = state.query_type
    if qt in (QueryType.SIMPLE_FACTUAL, QueryType.CALCULATION):
        return "simple_rag"
    if qt in (QueryType.MULTI_HOP, QueryType.TREND_ANALYSIS):
        return "multi_hop"
    if qt == QueryType.COMPARATIVE:
        return "comparative"
    if qt == QueryType.REPORT_GENERATION:
        return "report"
    return "simple_rag"


class MeridianGraph:
    """Wraps the compiled LangGraph and exposes run/stream interfaces."""

    def __init__(self) -> None:
        self._router = QueryRouter()
        self._simple = SimpleRAGAgent()
        self._multi_hop = MultiHopAgent()
        self._comparative = ComparativeAgent()

        # Build graph
        builder = StateGraph(AgentState)
        builder.add_node("router", self._run_router)
        builder.add_node("simple_rag", self._run_simple)
        builder.add_node("multi_hop", self._run_multi_hop)
        builder.add_node("comparative", self._run_comparative)
        builder.add_node("report", self._run_report)

        builder.add_edge(START, "router")
        builder.add_conditional_edges("router", _route_decision)
        for node in ("simple_rag", "multi_hop", "comparative", "report"):
            builder.add_edge(node, END)

        self._graph = builder.compile()

    # ── Node implementations ──────────────────────────────────────
    def _run_router(self, state: AgentState) -> AgentState:
        return self._router.route(state)

    async def _run_simple(self, state: AgentState) -> AgentState:
        return await self._simple.run(state)

    async def _run_multi_hop(self, state: AgentState) -> AgentState:
        return await self._multi_hop.run(state)

    async def _run_comparative(self, state: AgentState) -> AgentState:
        return await self._comparative.run(state)

    async def _run_report(self, state: AgentState) -> AgentState:
        # Report mode uses multi-hop with extra context
        state = await self._multi_hop.run(state)
        return state

    # ── Public interfaces ─────────────────────────────────────────
    async def run(self, state: AgentState) -> AgentState:
        result = await self._graph.ainvoke(state)
        return AgentState(**result)

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        """
        Route and stream directly — bypasses LangGraph for streaming efficiency.
        """
        # Route first
        state = self._router.route(state)
        route = _route_decision(state)

        log.info("graph.streaming", route=route, query_type=state.query_type)

        if route == "simple_rag":
            async for token in self._simple.stream(state):
                yield token
        elif route == "multi_hop":
            async for token in self._multi_hop.stream(state):
                yield token
        elif route == "comparative":
            async for token in self._comparative.stream(state):
                yield token
        else:
            async for token in self._multi_hop.stream(state):
                yield token
