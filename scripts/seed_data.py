#!/usr/bin/env python3
"""
Seed Meridian with a set of well-known companies to bootstrap the knowledge base.

Usage:
  python scripts/seed_data.py
  python scripts/seed_data.py --tickers AAPL MSFT NVDA --years 2
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.processor import IngestionPipeline
from backend.knowledge_graph.client import KnowledgeGraphClient
from backend.database import init_schema

DEFAULT_TICKERS = [
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "NVDA",   # NVIDIA
    "GOOGL",  # Alphabet
    "AMZN",   # Amazon
    "META",   # Meta Platforms
    "TSLA",   # Tesla
    "JPM",    # JPMorgan Chase
    "V",      # Visa
    "UNH",    # UnitedHealth Group
]

# Pre-seeded competitor relationships
COMPETITOR_PAIRS = [
    ("AAPL", "MSFT"),
    ("AAPL", "GOOGL"),
    ("MSFT", "GOOGL"),
    ("NVDA", "AMD"),
    ("AMZN", "MSFT"),   # Cloud
    ("AMZN", "GOOGL"),  # Cloud
    ("META", "SNAP"),
    ("TSLA", "F"),
    ("TSLA", "GM"),
]

COMPANY_INFO = {
    "AAPL":  ("Apple Inc.", "Technology", "Consumer Electronics"),
    "MSFT":  ("Microsoft Corporation", "Technology", "Software"),
    "NVDA":  ("NVIDIA Corporation", "Technology", "Semiconductors"),
    "GOOGL": ("Alphabet Inc.", "Technology", "Internet Services"),
    "AMZN":  ("Amazon.com Inc.", "Consumer Discretionary", "E-Commerce"),
    "META":  ("Meta Platforms Inc.", "Technology", "Social Media"),
    "TSLA":  ("Tesla Inc.", "Consumer Discretionary", "Electric Vehicles"),
    "JPM":   ("JPMorgan Chase & Co.", "Financials", "Banking"),
    "V":     ("Visa Inc.", "Financials", "Payment Processing"),
    "UNH":   ("UnitedHealth Group", "Healthcare", "Health Insurance"),
    "AMD":   ("Advanced Micro Devices", "Technology", "Semiconductors"),
    "F":     ("Ford Motor Company", "Consumer Discretionary", "Automobiles"),
    "GM":    ("General Motors", "Consumer Discretionary", "Automobiles"),
    "SNAP":  ("Snap Inc.", "Technology", "Social Media"),
}


async def seed_kg(tickers: list[str]) -> None:
    kg = KnowledgeGraphClient()
    kg.init_schema()

    print("Seeding knowledge graph...")
    for ticker in tickers:
        if info := COMPANY_INFO.get(ticker):
            name, sector, industry = info
            kg.upsert_company(ticker, name, sector, industry)
            print(f"  ✓ {ticker}: {name}")

    for a, b in COMPETITOR_PAIRS:
        if a in tickers or b in tickers:
            # Ensure both nodes exist
            for t in (a, b):
                if info := COMPANY_INFO.get(t):
                    kg.upsert_company(t, *info)
            kg.add_competitor(a, b)
            print(f"  ↔ {a} <-> {b}")
    print("Knowledge graph seeded.\n")


async def seed_filings(tickers: list[str], years: int) -> None:
    pipeline = IngestionPipeline()
    for ticker in tickers:
        print(f"Ingesting {ticker}...")
        result = await pipeline.ingest_ticker(ticker=ticker, years_back=years)
        print(
            f"  ✓ {ticker}: {result['documents_ingested']} documents, "
            f"{result['chunks_indexed']} chunks indexed"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Meridian with financial data")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS[:3])  # default: 3 for quick start
    parser.add_argument("--years", type=int, default=2)
    parser.add_argument("--kg-only", action="store_true", help="Only seed knowledge graph")
    parser.add_argument("--filings-only", action="store_true", help="Only seed filings")
    args = parser.parse_args()

    print(f"Seeding Meridian with: {', '.join(args.tickers)} ({args.years} years)")
    print("=" * 60)

    await init_schema()

    if not args.filings_only:
        await seed_kg(args.tickers)

    if not args.kg_only:
        await seed_filings(args.tickers, args.years)

    print("\nSeeding complete!")


if __name__ == "__main__":
    asyncio.run(main())
