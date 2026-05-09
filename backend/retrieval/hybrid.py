"""Hybrid retrieval: dense (Pinecone) + sparse (Elasticsearch) fused via RRF."""
import asyncio
from typing import Any

import structlog

from backend.config import get_settings
from backend.ingestion.indexer import VoyageEmbedder
from backend.models.documents import ChunkMetadata, ChunkType, FilingSection, FilingType
from backend.models.queries import RetrievedChunk
from backend.retrieval.hyde import HyDEGenerator
from backend.retrieval.reranker import CrossEncoderReranker, ContextualCompressor
from backend.retrieval.temporal import DateFilter, TemporalResolver

log = structlog.get_logger()

RRF_K = 60  # constant for Reciprocal Rank Fusion


def _rrf_score(rank: int) -> float:
    return 1.0 / (RRF_K + rank)


def _fuse_results(
    dense: list[tuple[str, float, dict]],
    sparse: list[tuple[str, float, dict]],
) -> list[tuple[str, float, dict]]:
    """Reciprocal Rank Fusion of dense and sparse result lists."""
    scores: dict[str, float] = {}
    metas: dict[str, dict] = {}
    dense_scores: dict[str, float] = {}
    sparse_scores: dict[str, float] = {}

    for rank, (cid, score, meta) in enumerate(dense):
        scores[cid] = scores.get(cid, 0) + _rrf_score(rank)
        dense_scores[cid] = score
        metas[cid] = meta

    for rank, (cid, score, meta) in enumerate(sparse):
        scores[cid] = scores.get(cid, 0) + _rrf_score(rank)
        sparse_scores[cid] = score
        if cid not in metas:
            metas[cid] = meta

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        (cid, scores[cid], {**metas[cid], "_dense": dense_scores.get(cid, 0), "_sparse": sparse_scores.get(cid, 0)})
        for cid, _ in ranked
    ]


def _meta_to_chunk_metadata(meta: dict, chunk_id: str, text: str) -> ChunkMetadata:
    from datetime import datetime
    report_date = None
    if ts := meta.get("report_date_ts"):
        try:
            report_date = datetime.utcfromtimestamp(int(ts))
        except Exception:
            pass

    return ChunkMetadata(
        chunk_id=chunk_id,
        document_id=meta.get("document_id", ""),
        source_url=meta.get("source_url", ""),
        ticker=meta.get("ticker", ""),
        company_name=meta.get("company_name", ""),
        cik=meta.get("cik", ""),
        filing_type=FilingType(meta.get("filing_type", "10-K")),
        filing_section=FilingSection(meta.get("filing_section", "Other")),
        fiscal_period=meta.get("fiscal_period", ""),
        fiscal_year=meta.get("fiscal_year"),
        report_date=report_date,
        chunk_type=ChunkType(meta.get("chunk_type", "narrative")),
        financial_metrics_present=meta.get("financial_metrics", False),
        contains_guidance=meta.get("contains_guidance", False),
        sentiment_score=meta.get("sentiment"),
        word_count=meta.get("word_count", 0),
    )


class HybridRetriever:
    """
    Full retrieval pipeline:
    1. (Optional) HyDE — generate hypothetical document
    2. Dense search — Pinecone with metadata filter
    3. Sparse search — Elasticsearch BM25
    4. RRF fusion
    5. Cross-encoder rerank + temporal decay
    6. (Optional) contextual compression
    """

    def __init__(self, use_hyde: bool = True, use_compression: bool = False) -> None:
        settings = get_settings()
        self._embedder = VoyageEmbedder()
        self._temporal = TemporalResolver()
        self._reranker = CrossEncoderReranker()
        self._top_k = settings.retrieval_top_k
        self._rerank_k = settings.rerank_top_k
        self._use_hyde = use_hyde
        self._compressor = ContextualCompressor() if use_compression else None
        self._hyde = HyDEGenerator() if use_hyde else None

        # Lazy-init Pinecone + ES clients
        self._pinecone_index = None
        self._es_client = None
        self._es_index = None

    def _get_pinecone(self):
        if self._pinecone_index is None:
            from pinecone import Pinecone
            settings = get_settings()
            pc = Pinecone(api_key=settings.pinecone_api_key)
            self._pinecone_index = pc.Index(settings.pinecone_index_name)
        return self._pinecone_index

    def _get_es(self):
        if self._es_client is None:
            from elasticsearch import Elasticsearch
            settings = get_settings()
            self._es_client = Elasticsearch(settings.elasticsearch_url)
            self._es_index = settings.elasticsearch_index_name
        return self._es_client, self._es_index

    async def retrieve(
        self,
        query: str,
        ticker: str | None = None,
        date_filter: DateFilter | None = None,
        top_k: int | None = None,
        filing_type: str | None = None,
        use_rerank: bool = True,
    ) -> list[RetrievedChunk]:
        top_k = top_k or self._rerank_k
        if date_filter is None:
            date_filter = self._temporal.resolve(query)

        loop = asyncio.get_event_loop()

        # Generate query embedding (+ optional HyDE)
        query_text = query
        if self._use_hyde and self._hyde:
            hyde_text = await loop.run_in_executor(None, self._hyde.generate, query)
            # Embed both and average
            q_emb, h_emb = await asyncio.gather(
                loop.run_in_executor(None, self._embedder.embed_query, query),
                loop.run_in_executor(None, self._embedder.embed_query, hyde_text),
            )
            query_vec = [(q + h) / 2 for q, h in zip(q_emb, h_emb)]
        else:
            query_vec = await loop.run_in_executor(None, self._embedder.embed_query, query_text)

        # Build metadata filter
        pc_filter = self._temporal.to_pinecone_filter(date_filter, ticker)
        if filing_type:
            ft_filter = {"filing_type": {"$eq": filing_type}}
            pc_filter = {"$and": [pc_filter, ft_filter]} if pc_filter else ft_filter

        # Dense + sparse in parallel
        dense_results, sparse_results = await asyncio.gather(
            loop.run_in_executor(None, self._dense_search, query_vec, pc_filter),
            loop.run_in_executor(None, self._sparse_search, query, date_filter, ticker, filing_type),
        )

        # RRF fusion
        fused = _fuse_results(dense_results, sparse_results)

        # Build RetrievedChunk list
        chunks: list[RetrievedChunk] = []
        for cid, score, meta in fused[: self._top_k]:
            text = meta.get("text_preview", "") or meta.get("text", "")
            rc = RetrievedChunk(
                chunk_id=cid,
                text=text,
                metadata=_meta_to_chunk_metadata(meta, cid, text),
                score=score,
                dense_score=meta.get("_dense"),
                sparse_score=meta.get("_sparse"),
            )
            chunks.append(rc)

        # Fetch full text from ES (Pinecone only stores preview)
        chunks = await loop.run_in_executor(None, self._hydrate_text, chunks)

        # Rerank
        if use_rerank and chunks:
            chunks = await loop.run_in_executor(
                None, self._reranker.rerank, query, chunks, top_k
            )

        # Contextual compression
        if self._compressor and chunks:
            chunks = await loop.run_in_executor(None, self._compressor.compress, query, chunks)

        return chunks

    def _dense_search(
        self, query_vec: list[float], pc_filter: dict
    ) -> list[tuple[str, float, dict]]:
        index = self._get_pinecone()
        kwargs: dict[str, Any] = {
            "vector": query_vec,
            "top_k": self._top_k,
            "include_metadata": True,
        }
        if pc_filter:
            kwargs["filter"] = pc_filter
        resp = index.query(**kwargs)
        return [(m["id"], m["score"], m.get("metadata", {})) for m in resp.get("matches", [])]

    def _sparse_search(
        self,
        query: str,
        date_filter: DateFilter,
        ticker: str | None,
        filing_type: str | None,
    ) -> list[tuple[str, float, dict]]:
        es, idx = self._get_es()
        filters = self._temporal.to_es_filter(date_filter, ticker)
        if filing_type:
            filters.append({"term": {"filing_type": filing_type}})

        body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [{"multi_match": {"query": query, "fields": ["text^2", "company_name"]}}],
                    "filter": filters,
                }
            },
            "size": self._top_k,
        }
        resp = es.search(index=idx, body=body)
        results = []
        for hit in resp["hits"]["hits"]:
            meta = hit["_source"]
            meta["text"] = hit["_source"].get("text", "")
            results.append((hit["_id"], hit["_score"], meta))
        return results

    def _hydrate_text(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Replace short preview text with full chunk text from Elasticsearch."""
        if not chunks:
            return chunks
        es, idx = self._get_es()
        ids = [c.chunk_id for c in chunks]
        try:
            resp = es.mget(index=idx, body={"ids": ids})
            id_to_text = {
                doc["_id"]: doc["_source"].get("text", "")
                for doc in resp["docs"]
                if doc.get("found")
            }
            for chunk in chunks:
                if full := id_to_text.get(chunk.chunk_id):
                    chunk.text = full
        except Exception as exc:
            log.warning("retrieval.hydrate_failed", error=str(exc))
        return chunks
