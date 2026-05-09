"""Index DocumentChunks into Pinecone (dense) and Elasticsearch (sparse)."""
import asyncio
import json
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import get_settings
from backend.models.documents import DocumentChunk

log = structlog.get_logger()


class VoyageEmbedder:
    """Batch embedder using voyage-finance-2."""

    def __init__(self) -> None:
        import voyageai
        settings = get_settings()
        self._client = voyageai.Client(api_key=settings.voyage_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = self._client.embed(
            texts,
            model="voyage-finance-2",
            input_type="document",
        )
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:
        result = self._client.embed(
            [text],
            model="voyage-finance-2",
            input_type="query",
        )
        return result.embeddings[0]


class PineconeIndexer:
    """Upserts chunks into Pinecone with rich metadata filters."""

    def __init__(self) -> None:
        from pinecone import Pinecone
        settings = get_settings()
        pc = Pinecone(api_key=settings.pinecone_api_key)
        self._index = pc.Index(settings.pinecone_index_name)

    def upsert(self, chunks: list[DocumentChunk], embeddings: list[list[float]]) -> None:
        vectors = []
        for chunk, emb in zip(chunks, embeddings):
            m = chunk.metadata
            meta: dict[str, Any] = {
                "ticker": m.ticker,
                "company_name": m.company_name,
                "filing_type": m.filing_type.value,
                "filing_section": m.filing_section.value,
                "fiscal_period": m.fiscal_period,
                "fiscal_year": m.fiscal_year or 0,
                "chunk_type": m.chunk_type.value,
                "text_preview": chunk.text[:200],
                "financial_metrics": m.financial_metrics_present,
                "contains_guidance": m.contains_guidance,
                "sentiment": m.sentiment_score or 0.0,
                "source_url": m.source_url,
                "word_count": m.word_count,
            }
            if m.report_date:
                meta["report_date_ts"] = int(m.report_date.timestamp())
            vectors.append({"id": chunk.chunk_id, "values": emb, "metadata": meta})

        # Pinecone recommends batches of 100
        for i in range(0, len(vectors), 100):
            self._index.upsert(vectors=vectors[i : i + 100])

    def delete_by_ticker(self, ticker: str) -> None:
        self._index.delete(filter={"ticker": ticker})


class ElasticsearchIndexer:
    """Indexes chunk text into Elasticsearch for BM25 sparse retrieval."""

    def __init__(self) -> None:
        from elasticsearch import Elasticsearch
        settings = get_settings()
        self._es = Elasticsearch(settings.elasticsearch_url)
        self._index = settings.elasticsearch_index_name
        self._ensure_index()

    def _ensure_index(self) -> None:
        if not self._es.indices.exists(index=self._index):
            self._es.indices.create(
                index=self._index,
                body={
                    "settings": {
                        "analysis": {
                            "analyzer": {
                                "financial_analyzer": {
                                    "type": "custom",
                                    "tokenizer": "standard",
                                    "filter": ["lowercase", "stop", "snowball"],
                                }
                            }
                        }
                    },
                    "mappings": {
                        "properties": {
                            "text": {"type": "text", "analyzer": "financial_analyzer"},
                            "ticker": {"type": "keyword"},
                            "filing_type": {"type": "keyword"},
                            "fiscal_period": {"type": "keyword"},
                            "filing_section": {"type": "keyword"},
                            "chunk_type": {"type": "keyword"},
                            "report_date": {"type": "date"},
                            "financial_metrics": {"type": "boolean"},
                        }
                    },
                },
            )

    def bulk_index(self, chunks: list[DocumentChunk]) -> None:
        from elasticsearch.helpers import bulk
        actions = []
        for chunk in chunks:
            m = chunk.metadata
            actions.append({
                "_index": self._index,
                "_id": chunk.chunk_id,
                "_source": {
                    "text": chunk.text,
                    "ticker": m.ticker,
                    "filing_type": m.filing_type.value,
                    "fiscal_period": m.fiscal_period,
                    "filing_section": m.filing_section.value,
                    "chunk_type": m.chunk_type.value,
                    "report_date": m.report_date.isoformat() if m.report_date else None,
                    "financial_metrics": m.financial_metrics_present,
                    "company_name": m.company_name,
                    "source_url": m.source_url,
                },
            })
        if actions:
            bulk(self._es, actions)

    def delete_by_ticker(self, ticker: str) -> None:
        self._es.delete_by_query(
            index=self._index,
            body={"query": {"term": {"ticker": ticker}}},
        )


class DocumentIndexer:
    """Orchestrates embedding → Pinecone upsert + ES bulk index."""

    BATCH_SIZE = 50

    def __init__(self) -> None:
        self._embedder = VoyageEmbedder()
        self._pinecone = PineconeIndexer()
        self._es = ElasticsearchIndexer()

    async def index(self, chunks: list[DocumentChunk]) -> int:
        total = 0
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i : i + self.BATCH_SIZE]
            texts = [c.text for c in batch]

            # Run embedding in thread pool (synchronous SDK)
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, self._embedder.embed_batch, texts
            )

            # Attach embeddings
            for chunk, emb in zip(batch, embeddings):
                chunk.embedding = emb

            # Upsert to both stores
            await asyncio.get_event_loop().run_in_executor(
                None, self._pinecone.upsert, batch, embeddings
            )
            await asyncio.get_event_loop().run_in_executor(
                None, self._es.bulk_index, batch
            )

            total += len(batch)
            log.info("indexer.batch_indexed", indexed=total, total=len(chunks))

        return total
