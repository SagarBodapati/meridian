"""Ingestion management routes."""
import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.ingestion.processor import IngestionPipeline
from backend.models.queries import IngestRequest

router = APIRouter(prefix="/ingest", tags=["ingestion"])
_pipeline = IngestionPipeline()


@router.post("")
async def ingest_ticker(request: IngestRequest, background_tasks: BackgroundTasks):
    """Trigger async ingestion for a ticker. Returns immediately, ingests in background."""
    background_tasks.add_task(
        _pipeline.ingest_ticker,
        ticker=request.ticker,
        filing_types=request.filing_types,
        years_back=request.years_back,
        force_reingest=request.force_reingest,
    )
    return {
        "status": "queued",
        "ticker": request.ticker.upper(),
        "message": f"Ingestion started for {request.ticker.upper()}. Check /ingest/status/{request.ticker} for progress.",
    }


@router.post("/sync")
async def ingest_ticker_sync(request: IngestRequest):
    """Synchronous ingestion — waits for completion. Use for small jobs."""
    result = await _pipeline.ingest_ticker(
        ticker=request.ticker,
        filing_types=request.filing_types,
        years_back=request.years_back,
        force_reingest=request.force_reingest,
    )
    return result


@router.get("/status/{ticker}")
async def ingestion_status(ticker: str):
    """Return ingestion log entries for a ticker."""
    from backend.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT filing_type, fiscal_period, status, chunks_indexed, error_message,
                      started_at, completed_at
               FROM ingestion_log
               WHERE ticker = $1
               ORDER BY started_at DESC
               LIMIT 50""",
            ticker.upper(),
        )
    return {"ticker": ticker.upper(), "logs": [dict(r) for r in rows]}


@router.delete("/{ticker}")
async def delete_ticker_index(ticker: str):
    """Remove all indexed data for a ticker (Pinecone + ES + ingestion log)."""
    from backend.ingestion.indexer import PineconeIndexer, ElasticsearchIndexer
    from backend.database import get_pool

    loop = asyncio.get_event_loop()
    pi = PineconeIndexer()
    ei = ElasticsearchIndexer()
    await loop.run_in_executor(None, pi.delete_by_ticker, ticker.upper())
    await loop.run_in_executor(None, ei.delete_by_ticker, ticker.upper())

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ingestion_log WHERE ticker = $1", ticker.upper())

    return {"status": "deleted", "ticker": ticker.upper()}
