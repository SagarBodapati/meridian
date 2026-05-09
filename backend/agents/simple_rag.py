"""Simple RAG agent — single-document factual Q&A with streaming support."""
from typing import AsyncIterator

import structlog
from anthropic import Anthropic

from backend.agents.prompts import SIMPLE_RAG_SYSTEM
from backend.agents.state import AgentState
from backend.config import get_settings
from backend.models.queries import Citation, RetrievedChunk
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.temporal import TemporalResolver

log = structlog.get_logger()

MAX_CONTEXT_CHARS = 24_000  # ~6k tokens


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """Concatenate retrieved chunks with source labels."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        m = chunk.metadata
        label = f"[{i}] {m.company_name} {m.filing_type.value} {m.fiscal_period} — {m.filing_section.value}"
        parts.append(f"{label}\n{chunk.text}")
    context = "\n\n---\n\n".join(parts)
    return context[:MAX_CONTEXT_CHARS]


def _extract_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    seen: set[str] = set()
    citations = []
    for chunk in chunks:
        m = chunk.metadata
        key = f"{m.ticker}:{m.filing_type.value}:{m.fiscal_period}"
        if key not in seen:
            seen.add(key)
            citations.append(Citation(
                chunk_id=chunk.chunk_id,
                text=chunk.text[:200],
                source=f"{m.company_name} {m.filing_type.value} {m.fiscal_period}",
                filing_type=m.filing_type.value,
                company=m.company_name,
                fiscal_period=m.fiscal_period,
                page_number=m.page_number,
                url=m.source_url,
            ))
    return citations


class SimpleRAGAgent:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._retriever = HybridRetriever()
        self._temporal = TemporalResolver()
        self._model_standard = settings.model_standard
        self._model_simple = settings.model_simple

    async def run(self, state: AgentState) -> AgentState:
        ticker = state.tickers[0] if state.tickers else state.filters.get("ticker")
        date_filter = self._temporal.resolve(state.query)

        chunks = await self._retriever.retrieve(
            query=state.query,
            ticker=ticker,
            date_filter=date_filter,
        )
        state.retrieved_chunks = chunks

        if not chunks:
            state.answer = (
                "I couldn't find relevant financial documents for this query. "
                "Please ensure the company has been ingested or try a broader question."
            )
            return state

        context = _build_context(chunks)
        state.context_text = context

        messages = _build_messages(state.history, state.query, context)
        resp = self._client.messages.create(
            model=self._model_standard,
            max_tokens=1500,
            system=SIMPLE_RAG_SYSTEM,
            messages=messages,
        )
        state.answer = resp.content[0].text
        state.citations = _extract_citations(chunks)
        state.model_used = self._model_standard
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        """Yield text tokens as they arrive from the Claude API."""
        ticker = state.tickers[0] if state.tickers else state.filters.get("ticker")
        date_filter = self._temporal.resolve(state.query)

        chunks = await self._retriever.retrieve(
            query=state.query,
            ticker=ticker,
            date_filter=date_filter,
        )
        state.retrieved_chunks = chunks
        state.citations = _extract_citations(chunks)

        if not chunks:
            yield "I couldn't find relevant financial documents for this query."
            return

        context = _build_context(chunks)
        messages = _build_messages(state.history, state.query, context)

        with self._client.messages.stream(
            model=self._model_standard,
            max_tokens=1500,
            system=SIMPLE_RAG_SYSTEM,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text


def _build_messages(history, query: str, context: str) -> list[dict]:
    messages = []
    # Include last 6 turns of conversation history for context
    for msg in history[-6:]:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({
        "role": "user",
        "content": f"Retrieved context:\n\n{context}\n\n---\n\nQuestion: {query}",
    })
    return messages
