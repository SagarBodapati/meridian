"""Temporal resolver: parse relative date references in financial queries."""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class DateFilter:
    start: datetime | None = None
    end: datetime | None = None
    fiscal_periods: list[str] | None = None  # explicit period labels e.g. ["Q3-2024", "Q4-2024"]
    prefer_recency: bool = True


# Maps relative labels → approximate day offsets from today
RELATIVE_MAP = {
    "last quarter": 120,
    "previous quarter": 120,
    "most recent quarter": 90,
    "last year": 400,
    "past year": 400,
    "last 2 years": 730,
    "last 3 years": 1095,
    "last 5 years": 1825,
    "last 8 quarters": 730,
    "past 8 quarters": 730,
    "most recent": 120,
    "latest": 120,
    "recent": 180,
    "current year": 365,
    "this year": 365,
    "ytd": 365,
}

QUARTER_RE = re.compile(r"\b(Q[1-4])[- ]?(\d{4})\b", re.I)
FY_RE = re.compile(r"\b(FY|fiscal\s+year)\s*(\d{4})\b", re.I)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


class TemporalResolver:
    def resolve(self, query: str, today: datetime | None = None) -> DateFilter:
        now = today or datetime.utcnow()
        query_lower = query.lower()

        # Explicit quarter references: Q3 2024, Q3-2024
        explicit_periods = []
        for m in QUARTER_RE.finditer(query):
            explicit_periods.append(f"{m.group(1).upper()}-{m.group(2)}")

        # Explicit fiscal years: FY2024, fiscal year 2024
        for m in FY_RE.finditer(query):
            explicit_periods.append(f"FY{m.group(2)}")

        if explicit_periods:
            return DateFilter(fiscal_periods=explicit_periods, prefer_recency=False)

        # Relative references
        for phrase, days in RELATIVE_MAP.items():
            if phrase in query_lower:
                return DateFilter(
                    start=now - timedelta(days=days),
                    end=now,
                    prefer_recency=True,
                )

        # Bare year: "2023 results", "in 2022"
        years = YEAR_RE.findall(query)
        if years:
            year = int(years[0])
            return DateFilter(
                start=datetime(year, 1, 1),
                end=datetime(year, 12, 31),
                prefer_recency=False,
            )

        # Default: last 3 years (broad recall, reranker handles precision)
        return DateFilter(start=now - timedelta(days=1095), end=now, prefer_recency=True)

    def to_pinecone_filter(self, date_filter: DateFilter, ticker: str | None = None) -> dict:
        """Convert DateFilter to a Pinecone metadata filter dict."""
        conditions: list[dict] = []

        if ticker:
            conditions.append({"ticker": {"$eq": ticker.upper()}})

        if date_filter.fiscal_periods:
            conditions.append({"fiscal_period": {"$in": date_filter.fiscal_periods}})
        elif date_filter.start or date_filter.end:
            ts_filter: dict = {}
            if date_filter.start:
                ts_filter["$gte"] = int(date_filter.start.timestamp())
            if date_filter.end:
                ts_filter["$lte"] = int(date_filter.end.timestamp())
            if ts_filter:
                conditions.append({"report_date_ts": ts_filter})

        if not conditions:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def to_es_filter(self, date_filter: DateFilter, ticker: str | None = None) -> list[dict]:
        """Convert DateFilter to Elasticsearch filter clauses."""
        filters: list[dict] = []

        if ticker:
            filters.append({"term": {"ticker": ticker.upper()}})

        if date_filter.fiscal_periods:
            filters.append({"terms": {"fiscal_period": date_filter.fiscal_periods}})
        elif date_filter.start or date_filter.end:
            rng: dict = {}
            if date_filter.start:
                rng["gte"] = date_filter.start.isoformat()
            if date_filter.end:
                rng["lte"] = date_filter.end.isoformat()
            if rng:
                filters.append({"range": {"report_date": rng}})

        return filters
