"""Meridian FastAPI application entry point."""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import chat, ingest, reports, search
from backend.config import get_settings
from backend.database import init_schema

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("meridian.startup", environment=settings.environment)
    try:
        await init_schema()
        log.info("meridian.db_ready")
    except Exception as exc:
        log.warning("meridian.db_init_failed", error=str(exc))

    try:
        from backend.knowledge_graph.client import KnowledgeGraphClient
        KnowledgeGraphClient().init_schema()
        log.info("meridian.kg_ready")
    except Exception as exc:
        log.warning("meridian.kg_init_failed", error=str(exc))

    yield
    log.info("meridian.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Meridian — Financial Research Copilot",
        description="Advanced agentic RAG for financial research",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(ingest.router, prefix="/api/v1")
    app.include_router(search.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "meridian"}

    return app


app = create_app()
