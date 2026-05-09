"""Chat route — SSE streaming endpoint + non-streaming fallback."""
import json
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from backend.agents.graph import MeridianGraph
from backend.agents.state import AgentState
from backend.models.queries import ChatRequest, ChatResponse, QueryType

router = APIRouter(prefix="/chat", tags=["chat"])
_graph = MeridianGraph()


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Server-Sent Events streaming endpoint.
    Yields:
      - data: {"type": "token", "text": "..."}
      - data: {"type": "citations", "citations": [...]}
      - data: {"type": "done", "metadata": {...}}
    """
    session_id = request.session_id or str(uuid.uuid4())
    state = AgentState(
        query=request.message,
        session_id=session_id,
        history=request.history,
        filters=request.filters,
    )

    async def event_generator():
        start = time.perf_counter()
        try:
            async for token in _graph.stream(state):
                yield {
                    "event": "token",
                    "data": json.dumps({"type": "token", "text": token}),
                }

            # Send citations after answer completes
            citations_payload = [c.model_dump() for c in (state.citations or [])]
            yield {
                "event": "citations",
                "data": json.dumps({"type": "citations", "citations": citations_payload}),
            }

            latency = int((time.perf_counter() - start) * 1000)
            yield {
                "event": "done",
                "data": json.dumps({
                    "type": "done",
                    "session_id": session_id,
                    "query_type": state.query_type.value,
                    "retrieved_chunks": len(state.retrieved_chunks),
                    "latency_ms": latency,
                    "model_used": state.model_used,
                }),
            }
        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Non-streaming endpoint for programmatic use."""
    start = time.perf_counter()
    session_id = request.session_id or str(uuid.uuid4())
    state = AgentState(
        query=request.message,
        session_id=session_id,
        history=request.history,
        filters=request.filters,
    )
    result = await _graph.run(state)
    latency = int((time.perf_counter() - start) * 1000)

    return ChatResponse(
        session_id=session_id,
        answer=result.answer,
        citations=result.citations,
        query_type=result.query_type,
        retrieved_chunks=len(result.retrieved_chunks),
        latency_ms=latency,
        model_used=result.model_used,
    )
