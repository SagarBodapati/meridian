from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class FilingType(str, Enum):
    K10 = "10-K"
    Q10 = "10-Q"
    K8 = "8-K"
    DEF14A = "DEF14A"
    S1 = "S-1"
    TRANSCRIPT = "transcript"
    NEWS = "news"
    ANALYST_REPORT = "analyst_report"


class ChunkType(str, Enum):
    NARRATIVE = "narrative"
    TABLE = "table"
    FOOTNOTE = "footnote"
    EXHIBIT = "exhibit"
    SUMMARY = "summary"


class FilingSection(str, Enum):
    MDA = "MD&A"
    RISK_FACTORS = "Risk Factors"
    FINANCIAL_STATEMENTS = "Financial Statements"
    NOTES = "Notes to Financial Statements"
    BUSINESS = "Business"
    PROPERTIES = "Properties"
    LEGAL = "Legal Proceedings"
    EXECUTIVE_COMP = "Executive Compensation"
    COVER = "Cover Page"
    OTHER = "Other"


class ChunkMetadata(BaseModel):
    """Metadata attached to every indexed chunk."""
    # Identity
    chunk_id: str
    document_id: str
    source_url: str = ""

    # Company
    ticker: str
    company_name: str
    cik: str = ""

    # Filing
    filing_type: FilingType
    filing_section: FilingSection = FilingSection.OTHER
    fiscal_period: str = ""          # e.g. "Q3-2024"
    fiscal_year: int | None = None
    report_date: datetime | None = None
    filing_date: datetime | None = None

    # Chunk properties
    chunk_type: ChunkType = ChunkType.NARRATIVE
    page_number: int | None = None
    char_start: int | None = None
    char_end: int | None = None

    # Enrichment
    entities_mentioned: list[str] = Field(default_factory=list)
    financial_metrics_present: bool = False
    contains_guidance: bool = False
    sentiment_score: float | None = None  # -1.0 to 1.0

    # Housekeeping
    ingestion_timestamp: datetime = Field(default_factory=datetime.utcnow)
    word_count: int = 0


class DocumentChunk(BaseModel):
    """A single indexed unit — text + metadata + optional structured data."""
    chunk_id: str
    text: str
    metadata: ChunkMetadata
    structured_data: dict[str, Any] | None = None  # for table chunks
    embedding: list[float] | None = None
    parent_chunk_id: str | None = None  # for hierarchical retrieval


class IngestedDocument(BaseModel):
    """Full document record before chunking."""
    document_id: str
    ticker: str
    company_name: str
    cik: str
    filing_type: FilingType
    fiscal_period: str
    report_date: datetime
    filing_date: datetime
    source_url: str
    raw_text: str
    tables: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
