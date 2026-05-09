"""Multi-hop reasoning agent — decomposes complex questions into sub-queries."""
import json
import re
from typing import AsyncIterator

import structlog
from anthropic import Anthropic

from backend.agents.prompts import (
    DECOMPOSITION_PROMPT,
    MULTI_HOP_SYSTEM,
    SYNTHESIS_PROMPT,
    TREND_SYSTEM,
)
from backend.agents.simple_rag import SimpleRAGAgent, _build_context, _extract_citations
from backend.agents.state import AgentState
from backend.config import get_settings
from backend.models.queries import QueryType
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.temporal import TemporalResolver

log = structlog.get_logger()


class MultiHopAgent:
    """
    Breaks a complex question into sub-questions, answers each via retrieval,
    then synthesizes a final answer.

    For trend analysis, it retrieves per-period data and computes growth rates.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._retriever = HybridRetriever()
        self._temporal = TemporalResolver()
        self._rag = SimpleRAGAgent()
        self._model = settings.model_standard
        self._model_complex = settings.model_complex

    async def run(self, state: AgentState) -> AgentState:
        sub_queries = await self._decompose(state.query)
        state.sub_queries = sub_queries
        log.info("multi_hop.sub_queries", count=len(sub_queries), queries=sub_queries)

        sub_answers: list[str] = []
        all_chunks = []

        for sub_q in sub_queries:
            sub_state = AgentState(
                query=sub_q,
                tickers=state.tickers,
                filters=state.filters,
                history=state.history,
            )
            sub_state = await self._rag.run(sub_state)
            sub_answers.append(f"Q: {sub_q}\nA: {sub_state.answer}")
            all_chunks.extend(sub_state.retrieved_chunks)
            state.intermediate_answers.append(sub_state.answer)

        state.retrieved_chunks = all_chunks
        state.citations = _extract_citations(all_chunks)

        # Synthesize
        system = TREND_SYSTEM if state.query_type == QueryType.TREND_ANALYSIS else MULTI_HOP_SYSTEM
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            query=state.query,
            sub_qa="\n\n".join(sub_answers),
        )
        resp = self._client.messages.create(
            model=self._model_complex,
            max_tokens=2500,
            system=system,
            messages=[{"role": "user", "content": synthesis_prompt}],
        )
        state.answer = resp.content[0].text
        state.model_used = self._model_complex
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        sub_queries = await self._decompose(state.query)
        state.sub_queries = sub_queries

        sub_answers = []
        all_chunks = []

        yield f"*Analyzing {len(sub_queries)} sub-questions...*\n\n"

        for i, sub_q in enumerate(sub_queries, 1):
            yield f"**Step {i}:** {sub_q}\n"
            sub_state = AgentState(
                query=sub_q,
                tickers=state.tickers,
                filters=state.filters,
            )
            sub_state = await self._rag.run(sub_state)
            sub_answers.append(f"Q: {sub_q}\nA: {sub_state.answer}")
            all_chunks.extend(sub_state.retrieved_chunks)

        state.retrieved_chunks = all_chunks
        state.citations = _extract_citations(all_chunks)

        yield "\n---\n\n**Synthesis:**\n\n"

        system = TREND_SYSTEM if state.query_type == QueryType.TREND_ANALYSIS else MULTI_HOP_SYSTEM
        synthesis_prompt = SYNTHESIS_PROMPT.format(
            query=state.query,
            sub_qa="\n\n".join(sub_answers),
        )
        with self._client.messages.stream(
            model=self._model_complex,
            max_tokens=2500,
            system=system,
            messages=[{"role": "user", "content": synthesis_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    async def _decompose(self, query: str) -> list[str]:
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                messages=[{"role": "user", "content": DECOMPOSITION_PROMPT.format(query=query)}],
            )
            raw = resp.content[0].text
            json_match = re.search(r"\[[\s\S]+\]", raw)
            if json_match:
                sub_queries = json.loads(json_match.group())
                return sub_queries[:4]  # cap at 4 sub-questions
        except Exception as exc:
            log.warning("multi_hop.decompose_failed", error=str(exc))
        return [query]  # fallback: treat as single query
