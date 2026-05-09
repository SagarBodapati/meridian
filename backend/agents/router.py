"""Query classifier — routes incoming questions to the right agent path."""
import json
import re

import structlog
from anthropic import Anthropic

from backend.agents.state import AgentState
from backend.config import get_settings
from backend.models.queries import QueryType

log = structlog.get_logger()

ROUTER_SYSTEM = """You are a financial research query classifier.
Analyze the user's question and output a JSON object with:
{
  "query_type": one of ["simple_factual", "multi_hop", "comparative", "trend_analysis", "calculation", "report_generation"],
  "tickers": [list of stock tickers mentioned or implied],
  "needs_calculation": true/false,
  "needs_multiple_documents": true/false,
  "time_range": "single_period" | "multi_period" | "open",
  "reasoning": "one sentence"
}

Definitions:
- simple_factual: Single fact from a single filing (revenue in Q3, CEO name, etc.)
- multi_hop: Requires chaining across multiple documents or reasoning steps
- comparative: Side-by-side analysis of 2+ companies or periods
- trend_analysis: How a metric changed over multiple time periods
- calculation: Requires arithmetic on extracted values (FCF yield, growth rate, etc.)
- report_generation: User wants a comprehensive research report
"""

# Regex fallback patterns
COMPARISON_RE = re.compile(r"\bvs\.?\b|\bversus\b|\bcompare\b|\bcompared\b", re.I)
TREND_RE = re.compile(r"\btrend\b|\bover\s+time\b|\bhistor\w+\b|\bquarters?\b|\byears?\b", re.I)
CALC_RE = re.compile(r"\byield\b|\bratio\b|\bgrowth\s+rate\b|\bcagr\b|\bmargin\b|\bcalculate\b", re.I)
REPORT_RE = re.compile(r"\breport\b|\banalysis\b|\bsummary\b|\boverview\b|\bresearch\b", re.I)
TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")


def _fallback_classify(query: str) -> QueryType:
    q = query.lower()
    if REPORT_RE.search(q):
        return QueryType.REPORT_GENERATION
    if COMPARISON_RE.search(q):
        return QueryType.COMPARATIVE
    if TREND_RE.search(q):
        return QueryType.TREND_ANALYSIS
    if CALC_RE.search(q):
        return QueryType.CALCULATION
    return QueryType.SIMPLE_FACTUAL


class QueryRouter:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.model_simple

    def route(self, state: AgentState) -> AgentState:
        query = state.query
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=300,
                system=ROUTER_SYSTEM,
                messages=[{"role": "user", "content": query}],
            )
            raw = resp.content[0].text
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]+\}", raw)
            if json_match:
                parsed = json.loads(json_match.group())
                state.query_type = QueryType(parsed.get("query_type", "simple_factual"))
                state.tickers = [t.upper() for t in parsed.get("tickers", [])]
            else:
                state.query_type = _fallback_classify(query)
        except Exception as exc:
            log.warning("router.classify_failed", error=str(exc))
            state.query_type = _fallback_classify(query)

        # Always try to extract tickers from query text as supplement
        if not state.tickers:
            state.tickers = _extract_tickers_from_text(query)

        # Override with explicit filter tickers
        if filter_ticker := state.filters.get("ticker"):
            if filter_ticker.upper() not in state.tickers:
                state.tickers.insert(0, filter_ticker.upper())

        log.info(
            "router.classified",
            query_type=state.query_type,
            tickers=state.tickers,
        )
        return state


def _extract_tickers_from_text(query: str) -> list[str]:
    """Heuristic: uppercase 2-5 letter words that look like tickers."""
    # Common English words to exclude
    EXCLUDE = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER",
               "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW",
               "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO", "BOY",
               "DID", "INC", "LLC", "CEO", "CFO", "COO", "EPS", "YOY", "QOQ", "IPO",
               "SEC", "ETF", "ESG", "API", "AWS", "GDP", "CPI", "FCF", "DCF", "P/E"}
    tickers = []
    for m in TICKER_RE.finditer(query):
        candidate = m.group(1)
        if candidate not in EXCLUDE and len(candidate) >= 2:
            tickers.append(candidate)
    return list(dict.fromkeys(tickers))  # deduplicate preserving order
