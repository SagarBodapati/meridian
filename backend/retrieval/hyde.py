"""HyDE — Hypothetical Document Embeddings.

Improves recall for complex financial queries by generating a plausible
answer, embedding that answer, and using it as the retrieval query vector.
This bridges the vocabulary gap between short queries and long-form filing text.
"""
import structlog
from anthropic import Anthropic

from backend.config import get_settings

log = structlog.get_logger()

HYDE_SYSTEM = """You are a financial document expert. Given a question about a company's
financial performance, write a brief (2-3 sentence) passage that would appear in an SEC filing
or earnings call transcript that directly answers the question. Write in the style of a formal
financial document. Do not make up specific numbers — use placeholder language like
"[METRIC] increased/decreased by [X]%". Focus on matching the vocabulary and structure of
real financial disclosures."""


class HyDEGenerator:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_simple  # haiku is fast and cheap for this

    def generate(self, query: str) -> str:
        """Generate a hypothetical document passage for the query."""
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=HYDE_SYSTEM,
                messages=[{"role": "user", "content": f"Question: {query}"}],
            )
            hyde_text = msg.content[0].text
            log.debug("hyde.generated", query=query[:80], hyde_preview=hyde_text[:100])
            return hyde_text
        except Exception as exc:
            log.warning("hyde.failed", error=str(exc))
            return query  # fallback to original query
