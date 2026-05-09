"""Comparative analysis agent — parallel retrieval across multiple companies."""
import asyncio
from typing import AsyncIterator

import structlog
from anthropic import Anthropic

from backend.agents.prompts import COMPARATIVE_SYSTEM
from backend.agents.simple_rag import _build_context, _extract_citations
from backend.agents.state import AgentState
from backend.config import get_settings
from backend.models.queries import RetrievedChunk
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.temporal import TemporalResolver

log = structlog.get_logger()

COMPARATIVE_USER_TEMPLATE = """Compare the following companies based on the retrieved context:
{tickers}

Question: {query}

Context:
{context}

Provide a structured comparison with a data table where applicable, then a narrative analysis."""


class ComparativeAgent:
    """
    Retrieves context for each company in parallel, then uses Claude to
    generate a structured comparative analysis.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._retriever = HybridRetriever()
        self._temporal = TemporalResolver()
        self._model = settings.model_complex

    async def run(self, state: AgentState) -> AgentState:
        tickers = state.tickers or [state.filters.get("ticker", "")]
        date_filter = self._temporal.resolve(state.query)

        # Parallel retrieval per ticker
        tasks = [
            self._retriever.retrieve(
                query=state.query,
                ticker=ticker,
                date_filter=date_filter,
                top_k=5,  # fewer per company, more companies
            )
            for ticker in tickers
        ]
        results: list[list[RetrievedChunk]] = await asyncio.gather(*tasks)

        all_chunks: list[RetrievedChunk] = []
        per_company_context: list[str] = []

        for ticker, chunks in zip(tickers, results):
            all_chunks.extend(chunks)
            if chunks:
                company_ctx = _build_context(chunks)
                per_company_context.append(f"=== {ticker} ===\n{company_ctx}")
            else:
                per_company_context.append(f"=== {ticker} ===\n[No data found]")

        state.retrieved_chunks = all_chunks
        state.citations = _extract_citations(all_chunks)

        full_context = "\n\n".join(per_company_context)
        user_content = COMPARATIVE_USER_TEMPLATE.format(
            tickers=", ".join(tickers),
            query=state.query,
            context=full_context[:28000],
        )

        resp = self._client.messages.create(
            model=self._model,
            max_tokens=3000,
            system=COMPARATIVE_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        state.answer = resp.content[0].text
        state.model_used = self._model
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[str]:
        tickers = state.tickers or [state.filters.get("ticker", "")]
        date_filter = self._temporal.resolve(state.query)

        yield f"*Retrieving data for {', '.join(tickers)}...*\n\n"

        tasks = [
            self._retriever.retrieve(query=state.query, ticker=t, date_filter=date_filter, top_k=5)
            for t in tickers
        ]
        results = await asyncio.gather(*tasks)

        all_chunks = []
        per_company_context = []
        for ticker, chunks in zip(tickers, results):
            all_chunks.extend(chunks)
            ctx = _build_context(chunks) if chunks else "[No data found]"
            per_company_context.append(f"=== {ticker} ===\n{ctx}")

        state.retrieved_chunks = all_chunks
        state.citations = _extract_citations(all_chunks)

        full_context = "\n\n".join(per_company_context)
        user_content = COMPARATIVE_USER_TEMPLATE.format(
            tickers=", ".join(tickers),
            query=state.query,
            context=full_context[:28000],
        )

        with self._client.messages.stream(
            model=self._model,
            max_tokens=3000,
            system=COMPARATIVE_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        ) as stream:
            for text in stream.text_stream:
                yield text
