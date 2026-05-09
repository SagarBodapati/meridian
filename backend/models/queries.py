from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from .documents import ChunkMetadata


class QueryType(str, Enum):
    SIMPLE_FACTUAL = "simple_factual"
    MULTI_HOP = "multi_hop"
    COMPARATIVE = "comparative"
    TREND_ANALYSIS = "trend_analysis"
    CALCULATION = "calculation"
    REPORT_GENERATION = "report_generation"


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: ChunkMetadata
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    structured_data: dict[str, Any] | None = None


class Citation(BaseModel):
    chunk_id: str
    text: str
    source: str       # "Apple 10-K Q3-2024, MD&A"
    filing_type: str
    company: str
    fiscal_period: str
    page_number: int | None = None
    url: str = ""


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    citations: list[Citation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    history: list[ChatMessage] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)  # ticker, date_range, etc.
    mode: str = "auto"  # "auto" | "report" | "quick"


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[Citation]
    query_type: QueryType
    retrieved_chunks: int
    latency_ms: int
    model_used: str


class IngestRequest(BaseModel):
    ticker: str
    filing_types: list[str] = Field(default_factory=lambda: ["10-K", "10-Q"])
    years_back: int = 3
    force_reingest: bool = False


class SearchRequest(BaseModel):
    query: str
    ticker: str | None = None
    filing_type: str | None = None
    fiscal_period: str | None = None
    top_k: int = 10
