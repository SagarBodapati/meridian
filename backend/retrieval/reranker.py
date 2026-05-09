"""Cross-encoder reranker + temporal decay scoring."""
import math
from datetime import datetime

import structlog

from backend.models.queries import RetrievedChunk

log = structlog.get_logger()

DECAY_LAMBDA = 0.001  # controls how quickly old docs are penalized


def _days_old(chunk: RetrievedChunk) -> int:
    if chunk.metadata.report_date:
        delta = datetime.utcnow() - chunk.metadata.report_date
        return max(0, delta.days)
    return 365 * 3  # assume 3 years old if unknown


def temporal_decay(score: float, days: int) -> float:
    """Exponential decay: score * e^(-λ * days)."""
    return score * math.exp(-DECAY_LAMBDA * days)


class CrossEncoderReranker:
    """
    Uses sentence-transformers cross-encoder for precision reranking.
    Falls back to temporal-decayed vector scores if model unavailable.
    """

    _model = None

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            try:
                from sentence_transformers import CrossEncoder
                cls._model = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512)
                log.info("reranker.model_loaded", model="BAAI/bge-reranker-v2-m3")
            except Exception as exc:
                log.warning("reranker.model_unavailable", error=str(exc))
                cls._model = False
        return cls._model

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 8,
        use_temporal_decay: bool = True,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        model = self._get_model()

        if model:
            pairs = [[query, c.text] for c in chunks]
            scores = model.predict(pairs)
            for chunk, score in zip(chunks, scores):
                chunk.rerank_score = float(score)
        else:
            # No cross-encoder: use combined dense+sparse score
            for chunk in chunks:
                chunk.rerank_score = chunk.score

        # Apply temporal decay on top of rerank score
        if use_temporal_decay:
            for chunk in chunks:
                days = _days_old(chunk)
                chunk.rerank_score = temporal_decay(chunk.rerank_score or chunk.score, days)

        chunks.sort(key=lambda c: c.rerank_score or 0, reverse=True)
        return chunks[:top_k]


class ContextualCompressor:
    """
    Extracts only the query-relevant sentences from each chunk,
    reducing noise passed to the LLM.
    """

    def __init__(self) -> None:
        from anthropic import Anthropic
        from backend.config import get_settings
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_simple

    def compress(self, query: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Keep only sentences in each chunk that are relevant to the query."""
        compressed = []
        for chunk in chunks:
            relevant = self._extract_relevant(query, chunk.text)
            if relevant and len(relevant) > 50:
                chunk.text = relevant
            compressed.append(chunk)
        return compressed

    def _extract_relevant(self, query: str, text: str) -> str:
        if len(text) < 200:
            return text
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Extract only the sentences from the following passage that are "
                            f"directly relevant to answering: '{query}'\n\n"
                            f"Passage:\n{text[:800]}\n\n"
                            f"Return only the relevant sentences, verbatim. "
                            f"If nothing is relevant, return the first 2 sentences."
                        ),
                    }
                ],
            )
            return resp.content[0].text
        except Exception:
            return text
