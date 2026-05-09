"""Top-level ingestion pipeline orchestrator."""
import asyncio
from datetime import datetime

import structlog

from backend.database import get_pool
from backend.ingestion.chunker import FinancialChunker
from backend.ingestion.edgar import EdgarClient
from backend.ingestion.enricher import MetadataEnricher
from backend.ingestion.indexer import DocumentIndexer
from backend.models.documents import IngestedDocument

log = structlog.get_logger()


class IngestionPipeline:
    """
    Pipeline: EDGAR fetch → chunk → enrich → index.

    Each step is independent so stages can be swapped (e.g., replace EDGAR
    with an uploaded PDF) without changing the rest.
    """

    def __init__(self) -> None:
        self._edgar = EdgarClient()
        self._chunker = FinancialChunker()
        self._enricher = MetadataEnricher()
        self._indexer = DocumentIndexer()

    async def ingest_ticker(
        self,
        ticker: str,
        filing_types: list[str] | None = None,
        years_back: int = 3,
        force_reingest: bool = False,
    ) -> dict:
        pool = await get_pool()
        total_chunks = 0
        total_docs = 0

        async for doc in self._edgar.stream_filings(ticker, filing_types, years_back):
            # Skip already-indexed documents unless forced
            if not force_reingest:
                async with pool.acquire() as conn:
                    existing = await conn.fetchval(
                        "SELECT id FROM ingestion_log WHERE ticker=$1 AND fiscal_period=$2 AND filing_type=$3 AND status='completed'",
                        ticker, doc.fiscal_period, doc.filing_type.value,
                    )
                    if existing:
                        log.info("ingestion.skip_existing", ticker=ticker, period=doc.fiscal_period)
                        continue

            log_id = await self._start_log(pool, doc)
            try:
                chunks = await self._process_document(doc)
                total_chunks += len(chunks)
                total_docs += 1
                await self._complete_log(pool, log_id, len(chunks))
            except Exception as exc:
                await self._fail_log(pool, log_id, str(exc))
                log.error("ingestion.document_failed", ticker=ticker, error=str(exc))

        return {"ticker": ticker, "documents_ingested": total_docs, "chunks_indexed": total_chunks}

    async def ingest_document(self, doc: IngestedDocument) -> int:
        """Ingest a single pre-loaded document (e.g., uploaded PDF)."""
        chunks = await self._process_document(doc)
        return len(chunks)

    async def _process_document(self, doc: IngestedDocument) -> list:
        # Chunk
        chunks = self._chunker.chunk(doc)
        log.info("ingestion.chunked", ticker=doc.ticker, period=doc.fiscal_period, chunks=len(chunks))

        # Enrich
        chunks = [self._enricher.enrich(c) for c in chunks]

        # Index (embed → Pinecone + ES)
        n = await self._indexer.index(chunks)
        log.info("ingestion.indexed", ticker=doc.ticker, period=doc.fiscal_period, indexed=n)

        return chunks

    async def _start_log(self, pool, doc: IngestedDocument) -> int:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO ingestion_log (ticker, filing_type, fiscal_period, source_url, status)
                   VALUES ($1, $2, $3, $4, 'in_progress') RETURNING id""",
                doc.ticker, doc.filing_type.value, doc.fiscal_period, doc.source_url,
            )

    async def _complete_log(self, pool, log_id: int, chunks: int) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_log SET status='completed', chunks_indexed=$1, completed_at=NOW() WHERE id=$2",
                chunks, log_id,
            )

    async def _fail_log(self, pool, log_id: int, error: str) -> None:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE ingestion_log SET status='failed', error_message=$1, completed_at=NOW() WHERE id=$2",
                error, log_id,
            )
