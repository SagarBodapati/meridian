"""Metadata enrichment: NER, financial metric detection, sentiment scoring."""
import re
from typing import Any

import structlog

from backend.models.documents import DocumentChunk

log = structlog.get_logger()

# Common financial metric keywords
METRIC_KEYWORDS = re.compile(
    r"\b(revenue|sales|income|earnings|profit|loss|margin|ebitda|eps|cash\s+flow|"
    r"debt|equity|assets|liabilities|dividend|buyback|guidance|outlook)\b",
    re.I,
)

GUIDANCE_KEYWORDS = re.compile(
    r"\b(guidance|outlook|forecast|expect|anticipate|project|target|full.year|"
    r"next\s+quarter|going\s+forward|fiscal\s+\d{4})\b",
    re.I,
)

# Simple positive/negative word lists for financial sentiment
POSITIVE_WORDS = {
    "growth", "increase", "increased", "grew", "strong", "record", "exceeded",
    "beat", "outperform", "accelerat", "expansion", "profitable", "momentum",
    "robust", "solid", "favorable", "improvement", "improved", "higher",
}
NEGATIVE_WORDS = {
    "decline", "decreased", "fell", "drop", "weak", "miss", "disappoint",
    "headwind", "challenge", "uncertain", "risk", "loss", "deteriorat",
    "soften", "lower", "compress", "pressure", "difficult",
}

# Ticker-like patterns (2-5 uppercase letters, possibly in parentheses)
TICKER_PATTERN = re.compile(r"\b([A-Z]{2,5})\b")

# Dollar amount patterns
DOLLAR_PATTERN = re.compile(
    r"\$\s?(\d[\d,]*\.?\d*)\s?(billion|million|thousand|B|M|K)?\b", re.I
)


class MetadataEnricher:
    """Stateless enricher — spaCy is loaded lazily to avoid startup cost."""

    _nlp: Any = None

    @classmethod
    def _get_nlp(cls) -> Any:
        if cls._nlp is None:
            try:
                import spacy
                cls._nlp = spacy.load("en_core_web_lg")
            except Exception:
                cls._nlp = False  # disable NER gracefully
        return cls._nlp

    def enrich(self, chunk: DocumentChunk) -> DocumentChunk:
        text = chunk.text

        # Financial metric flag
        chunk.metadata.financial_metrics_present = bool(METRIC_KEYWORDS.search(text))

        # Guidance detection
        chunk.metadata.contains_guidance = bool(GUIDANCE_KEYWORDS.search(text))

        # Sentiment score
        chunk.metadata.sentiment_score = self._simple_sentiment(text)

        # Named entity extraction
        chunk.metadata.entities_mentioned = self._extract_entities(text)

        return chunk

    def _simple_sentiment(self, text: str) -> float:
        words = set(re.findall(r"\b\w+\b", text.lower()))
        pos = len(words & POSITIVE_WORDS)
        neg = len(words & NEGATIVE_WORDS)
        total = pos + neg
        if total == 0:
            return 0.0
        return round((pos - neg) / total, 3)

    def _extract_entities(self, text: str) -> list[str]:
        entities: set[str] = set()

        # Try spaCy NER first
        nlp = self._get_nlp()
        if nlp:
            try:
                doc = nlp(text[:1000])  # cap at 1000 chars for speed
                for ent in doc.ents:
                    if ent.label_ in ("ORG", "PERSON", "GPE", "PRODUCT"):
                        entities.add(ent.text.strip())
            except Exception:
                pass

        # Supplement with dollar amounts
        for m in DOLLAR_PATTERN.finditer(text):
            entities.add(m.group())

        return sorted(entities)[:20]  # cap at 20
