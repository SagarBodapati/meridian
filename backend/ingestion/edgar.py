"""SEC EDGAR ingestion — fetches filings via EDGAR full-text search and bulk APIs."""
import asyncio
import hashlib
import re
from datetime import datetime, timedelta
from typing import AsyncIterator

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config import get_settings
from backend.models.documents import FilingType, IngestedDocument

log = structlog.get_logger()

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
FILING_TYPE_MAP = {
    "10-K": FilingType.K10,
    "10-Q": FilingType.Q10,
    "8-K": FilingType.K8,
    "DEF 14A": FilingType.DEF14A,
    "S-1": FilingType.S1,
}


class EdgarClient:
    """Async SEC EDGAR client with rate limiting and retry logic."""

    def __init__(self) -> None:
        settings = get_settings()
        self._delay = settings.edgar_request_delay
        self._headers = {
            "User-Agent": settings.edgar_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self._semaphore = asyncio.Semaphore(5)  # max 5 concurrent requests

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _get(self, url: str, params: dict | None = None) -> dict:
        async with self._semaphore:
            await asyncio.sleep(self._delay)
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _get_text(self, url: str) -> str:
        async with self._semaphore:
            await asyncio.sleep(self._delay)
            async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.text

    async def get_cik(self, ticker: str) -> str:
        """Resolve ticker → CIK."""
        data = await self._get(f"{EDGAR_BASE}/submissions/CIK{ticker.upper()}.json")
        return data.get("cik", "")

    async def get_company_facts(self, ticker: str) -> dict:
        """Return XBRL concept facts for a company."""
        cik = await self.get_cik(ticker)
        return await self._get(f"{EDGAR_BASE}/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json")

    async def search_filings(
        self,
        ticker: str,
        form_types: list[str],
        years_back: int = 3,
    ) -> list[dict]:
        """Return a list of filing metadata objects."""
        cutoff = datetime.utcnow() - timedelta(days=365 * years_back)
        results: list[dict] = []

        for form in form_types:
            try:
                data = await self._get(
                    "https://efts.sec.gov/LATEST/search-index",
                    params={
                        "q": f'"{ticker}"',
                        "dateRange": "custom",
                        "startdt": cutoff.strftime("%Y-%m-%d"),
                        "forms": form,
                    },
                )
                hits = data.get("hits", {}).get("hits", [])
                results.extend(hits)
                log.info(
                    "edgar.search_results",
                    ticker=ticker,
                    form=form,
                    count=len(hits),
                )
            except Exception as exc:
                log.warning("edgar.search_failed", ticker=ticker, form=form, error=str(exc))

        return results

    async def get_filing_document(self, accession_number: str, cik: str) -> str:
        """Fetch the primary HTML/text document for a filing."""
        acc_clean = accession_number.replace("-", "")
        index_url = (
            f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/{accession_number}-index.json"
        )
        try:
            index = await self._get(index_url)
        except Exception:
            # Try the .htm index variant
            index_url = f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/"
            return ""

        # Find the primary document (10-K/10-Q/8-K body)
        for doc in index.get("documents", []):
            if doc.get("type") in ("10-K", "10-Q", "8-K", "S-1") or doc.get("sequence") == "1":
                doc_url = f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{acc_clean}/{doc['filename']}"
                return await self._get_text(doc_url)

        return ""

    async def stream_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        years_back: int = 3,
    ) -> AsyncIterator[IngestedDocument]:
        """Yield IngestedDocument objects for each filing found."""
        if form_types is None:
            form_types = ["10-K", "10-Q"]

        hits = await self.search_filings(ticker, form_types, years_back)

        for hit in hits:
            src = hit.get("_source", {})
            accession = src.get("accession_no", "")
            form = src.get("form_type", "")
            filed = src.get("file_date", "")
            period = src.get("period_of_report", "")
            entity = src.get("entity_name", ticker)
            cik = src.get("entity_id", "")

            try:
                raw_text = await self.get_filing_document(accession, cik)
                if not raw_text or len(raw_text) < 500:
                    continue

                # Derive fiscal period label
                fiscal_period = _parse_fiscal_period(period, form)

                doc_id = hashlib.sha256(f"{ticker}:{accession}".encode()).hexdigest()[:16]

                yield IngestedDocument(
                    document_id=doc_id,
                    ticker=ticker.upper(),
                    company_name=entity,
                    cik=cik,
                    filing_type=FILING_TYPE_MAP.get(form, FilingType.K10),
                    fiscal_period=fiscal_period,
                    report_date=_parse_date(period),
                    filing_date=_parse_date(filed),
                    source_url=f"{EDGAR_BASE}/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{accession}-index.htm",
                    raw_text=raw_text,
                )
                log.info("edgar.filing_fetched", ticker=ticker, period=fiscal_period, form=form)

            except Exception as exc:
                log.warning(
                    "edgar.filing_fetch_failed",
                    ticker=ticker,
                    accession=accession,
                    error=str(exc),
                )


def _parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime.utcnow()


def _parse_fiscal_period(period_str: str, form: str) -> str:
    """Convert '2024-09-28' + '10-Q' → 'Q3-2024'."""
    dt = _parse_date(period_str)
    if "10-K" in form:
        return f"FY{dt.year}"
    # Quarter from month
    month = dt.month
    if month <= 3:
        q = "Q1"
    elif month <= 6:
        q = "Q2"
    elif month <= 9:
        q = "Q3"
    else:
        q = "Q4"
    return f"{q}-{dt.year}"
