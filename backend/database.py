"""PostgreSQL (TimescaleDB) schema bootstrap and async connection pool."""
import asyncpg
import structlog
from backend.config import get_settings

log = structlog.get_logger()
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)
    return _pool


async def init_schema() -> None:
    """Create tables if they don't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                ticker          TEXT PRIMARY KEY,
                company_name    TEXT NOT NULL,
                cik             TEXT,
                sic_code        TEXT,
                sector          TEXT,
                industry        TEXT,
                exchange        TEXT,
                country         TEXT DEFAULT 'US',
                fiscal_year_end TEXT DEFAULT '12-31',
                market_cap_usd  DOUBLE PRECISION,
                description     TEXT,
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS financial_metrics (
                id              BIGSERIAL PRIMARY KEY,
                ticker          TEXT NOT NULL,
                metric_name     TEXT NOT NULL,
                value           DOUBLE PRECISION NOT NULL,
                unit            TEXT DEFAULT 'USD',
                scale           TEXT DEFAULT 'millions',
                fiscal_period   TEXT NOT NULL,
                fiscal_year     INT NOT NULL,
                period_end_date DATE NOT NULL,
                segment         TEXT,
                source_chunk_id TEXT,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_ticker_period
                ON financial_metrics (ticker, fiscal_period);

            CREATE TABLE IF NOT EXISTS ingestion_log (
                id              BIGSERIAL PRIMARY KEY,
                ticker          TEXT NOT NULL,
                filing_type     TEXT NOT NULL,
                fiscal_period   TEXT NOT NULL,
                source_url      TEXT,
                status          TEXT DEFAULT 'pending',
                chunks_indexed  INT DEFAULT 0,
                error_message   TEXT,
                started_at      TIMESTAMPTZ DEFAULT NOW(),
                completed_at    TIMESTAMPTZ
            );

            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                last_active     TIMESTAMPTZ DEFAULT NOW(),
                message_count   INT DEFAULT 0,
                metadata        JSONB DEFAULT '{}'
            );
        """)
        # Make financial_metrics a hypertable for time-series queries
        try:
            await conn.execute(
                "SELECT create_hypertable('financial_metrics', 'period_end_date', if_not_exists => TRUE);"
            )
        except Exception:
            pass  # TimescaleDB not available, plain Postgres is fine
    log.info("database.schema_initialized")
