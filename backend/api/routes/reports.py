"""Report generation and company profile routes."""
from fastapi import APIRouter

from backend.agents.graph import MeridianGraph
from backend.agents.state import AgentState
from backend.knowledge_graph.client import KnowledgeGraphClient
from backend.models.queries import QueryType
from backend.tools.news import NewsSearcher

router = APIRouter(prefix="/reports", tags=["reports"])
_graph = MeridianGraph()
_kg = KnowledgeGraphClient()
_news = NewsSearcher()


@router.get("/company/{ticker}")
async def company_profile(ticker: str):
    """Return KG-enriched company profile + recent news."""
    ticker = ticker.upper()
    executives = _kg.get_executives(ticker)
    competitors = _kg.get_competitors(ticker)
    peer_set = _kg.get_peer_set(ticker)
    news = await _news.search(ticker, ticker=ticker, max_results=5)

    return {
        "ticker": ticker,
        "executives": executives,
        "competitors": competitors,
        "peer_set": peer_set,
        "recent_news": [
            {"title": n.title, "url": n.url, "published": n.published.isoformat(), "source": n.source}
            for n in news
        ],
    }


@router.post("/generate")
async def generate_report(ticker: str, period: str | None = None):
    """Generate a comprehensive research report for a company."""
    query = f"Generate a comprehensive financial research report for {ticker}"
    if period:
        query += f" for {period}"

    state = AgentState(
        query=query,
        tickers=[ticker.upper()],
        query_type=QueryType.REPORT_GENERATION,
    )
    result = await _graph.run(state)

    return {
        "ticker": ticker.upper(),
        "period": period,
        "report": result.answer,
        "citations": [c.model_dump() for c in result.citations],
        "model_used": result.model_used,
    }


@router.get("/metrics/{ticker}")
async def company_metrics(ticker: str, periods: int = 8):
    """Return raw financial metrics time series from the metric store."""
    from backend.database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT metric_name, value, unit, scale, fiscal_period, fiscal_year,
                      period_end_date, segment
               FROM financial_metrics
               WHERE ticker = $1
               ORDER BY period_end_date DESC
               LIMIT $2""",
            ticker.upper(), periods * 10,  # multiple metrics per period
        )
    return {"ticker": ticker.upper(), "metrics": [dict(r) for r in rows]}
