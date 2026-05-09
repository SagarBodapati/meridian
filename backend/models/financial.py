from datetime import date
from pydantic import BaseModel, Field


class FinancialMetric(BaseModel):
    """A single numeric metric extracted from a filing."""
    ticker: str
    company_name: str
    metric_name: str          # "revenue", "gross_profit", "net_income", …
    value: float
    unit: str = "USD"         # "USD", "shares", "percent", …
    scale: str = "millions"   # "units", "thousands", "millions", "billions"
    fiscal_period: str        # "Q3-2024"
    fiscal_year: int
    period_end_date: date
    segment: str | None = None  # "Services", "iPhone", …
    source_chunk_id: str = ""


class Company(BaseModel):
    ticker: str
    company_name: str
    cik: str = ""
    sic_code: str = ""
    sector: str = ""
    industry: str = ""
    exchange: str = ""
    country: str = "US"
    fiscal_year_end: str = "12-31"  # MM-DD
    market_cap_usd: float | None = None
    description: str = ""


class EarningsEstimate(BaseModel):
    ticker: str
    fiscal_period: str
    consensus_eps: float | None = None
    consensus_revenue: float | None = None
    num_analysts: int = 0
    eps_high: float | None = None
    eps_low: float | None = None
    revenue_high: float | None = None
    revenue_low: float | None = None
    estimate_date: date | None = None


class FiscalCalendar(BaseModel):
    ticker: str
    fiscal_year_end_month: int  # 12 for December
    quarters: list[dict[str, str]] = Field(default_factory=list)
    # e.g. [{"period": "Q1-2024", "start": "2024-01-01", "end": "2024-03-31", "report_date": "2024-04-25"}]
