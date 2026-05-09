"""Direct search route — bypasses agents for raw chunk retrieval."""
from fastapi import APIRouter

from backend.models.queries import SearchRequest
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.temporal import TemporalResolver

router = APIRouter(prefix="/search", tags=["search"])
_retriever = HybridRetriever(use_hyde=False, use_compression=False)
_temporal = TemporalResolver()


@router.post("")
async def search(request: SearchRequest):
    date_filter = _temporal.resolve(request.query)
    chunks = await _retriever.retrieve(
        query=request.query,
        ticker=request.ticker,
        date_filter=date_filter,
        filing_type=request.filing_type,
        top_k=request.top_k,
        use_rerank=True,
    )
    return {
        "query": request.query,
        "total": len(chunks),
        "results": [
            {
                "chunk_id": c.chunk_id,
                "text": c.text[:500],
                "score": round(c.score, 4),
                "rerank_score": round(c.rerank_score or 0, 4),
                "ticker": c.metadata.ticker,
                "filing_type": c.metadata.filing_type.value,
                "fiscal_period": c.metadata.fiscal_period,
                "section": c.metadata.filing_section.value,
                "source_url": c.metadata.source_url,
            }
            for c in chunks
        ],
    }
