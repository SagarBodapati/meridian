"""Shared LangGraph state definition for the Meridian agent graph."""
from typing import Annotated, Any
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages

from backend.models.queries import ChatMessage, Citation, QueryType, RetrievedChunk


class AgentState(BaseModel):
    """State passed through every node in the LangGraph workflow."""

    # Input
    query: str = ""
    session_id: str = ""
    history: list[ChatMessage] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)

    # Routing
    query_type: QueryType = QueryType.SIMPLE_FACTUAL
    tickers: list[str] = Field(default_factory=list)   # extracted company tickers
    sub_queries: list[str] = Field(default_factory=list)  # decomposed sub-questions

    # Retrieval
    retrieved_chunks: list[RetrievedChunk] = Field(default_factory=list)
    context_text: str = ""

    # Intermediate reasoning (multi-hop)
    intermediate_answers: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)

    # Output
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    model_used: str = ""
    error: str = ""

    class Config:
        arbitrary_types_allowed = True
