"""Celery worker — async ingestion tasks."""
from celery import Celery
from backend.config import get_settings

settings = get_settings()
celery_app = Celery("meridian", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "backend.worker.ingest_ticker_task": {"queue": "ingestion"},
        "backend.worker.ingest_ticker_task_force": {"queue": "ingestion"},
    },
)


@celery_app.task(name="backend.worker.ingest_ticker_task", bind=True, max_retries=2)
def ingest_ticker_task(self, ticker: str, filing_types: list[str], years_back: int):
    """Celery task wrapper for async ingestion pipeline."""
    import asyncio
    from backend.ingestion.processor import IngestionPipeline

    pipeline = IngestionPipeline()
    try:
        result = asyncio.run(
            pipeline.ingest_ticker(ticker=ticker, filing_types=filing_types, years_back=years_back)
        )
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
