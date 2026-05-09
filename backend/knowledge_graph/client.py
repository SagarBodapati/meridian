"""Neo4j knowledge graph client — company relationships, sector taxonomy."""
from contextlib import contextmanager
from typing import Any

import structlog
from neo4j import GraphDatabase, Driver

from backend.config import get_settings

log = structlog.get_logger()

_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


class KnowledgeGraphClient:
    def __init__(self) -> None:
        self._driver = get_driver()

    def run(self, cypher: str, **params) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [dict(record) for record in result]

    # ── Schema bootstrap ──────────────────────────────────────────
    def init_schema(self) -> None:
        constraints = [
            "CREATE CONSTRAINT company_ticker IF NOT EXISTS FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
            "CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE",
            "CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
        ]
        for stmt in constraints:
            try:
                self.run(stmt)
            except Exception as exc:
                log.debug("kg.constraint_skip", error=str(exc))
        log.info("kg.schema_initialized")

    # ── Company operations ────────────────────────────────────────
    def upsert_company(
        self,
        ticker: str,
        name: str,
        sector: str = "",
        industry: str = "",
        market_cap: float | None = None,
    ) -> None:
        self.run(
            """
            MERGE (c:Company {ticker: $ticker})
            SET c.name = $name,
                c.sector = $sector,
                c.industry = $industry,
                c.market_cap = $market_cap,
                c.updated_at = datetime()
            """,
            ticker=ticker, name=name, sector=sector, industry=industry, market_cap=market_cap,
        )
        if sector:
            self.run(
                """
                MERGE (s:Sector {name: $sector})
                WITH s
                MATCH (c:Company {ticker: $ticker})
                MERGE (c)-[:IN_SECTOR]->(s)
                """,
                sector=sector, ticker=ticker,
            )

    def add_competitor(self, ticker_a: str, ticker_b: str) -> None:
        self.run(
            """
            MATCH (a:Company {ticker: $a}), (b:Company {ticker: $b})
            MERGE (a)-[:COMPETES_WITH]-(b)
            """,
            a=ticker_a, b=ticker_b,
        )

    def add_executive(self, ticker: str, name: str, role: str) -> None:
        self.run(
            """
            MERGE (p:Person {name: $name})
            SET p.updated_at = datetime()
            WITH p
            MATCH (c:Company {ticker: $ticker})
            MERGE (p)-[r:ROLE_AT]->(c)
            SET r.role = $role, r.updated_at = datetime()
            """,
            ticker=ticker, name=name, role=role,
        )

    # ── Query operations ──────────────────────────────────────────
    def get_competitors(self, ticker: str) -> list[str]:
        results = self.run(
            """
            MATCH (c:Company {ticker: $ticker})-[:COMPETES_WITH]-(peer:Company)
            RETURN peer.ticker AS ticker
            """,
            ticker=ticker,
        )
        return [r["ticker"] for r in results]

    def get_executives(self, ticker: str) -> list[dict]:
        return self.run(
            """
            MATCH (p:Person)-[r:ROLE_AT]->(c:Company {ticker: $ticker})
            RETURN p.name AS name, r.role AS role
            """,
            ticker=ticker,
        )

    def get_peer_set(self, ticker: str, max_peers: int = 5) -> list[str]:
        """Return peer companies in same sector + explicit competitors."""
        results = self.run(
            """
            MATCH (c:Company {ticker: $ticker})-[:IN_SECTOR]->(s:Sector)<-[:IN_SECTOR]-(peer:Company)
            WHERE peer.ticker <> $ticker
            OPTIONAL MATCH (c)-[:COMPETES_WITH]-(comp:Company)
            RETURN DISTINCT peer.ticker AS ticker
            LIMIT $limit
            """,
            ticker=ticker, limit=max_peers,
        )
        return [r["ticker"] for r in results]

    def find_supply_chain(self, ticker: str) -> list[dict]:
        return self.run(
            """
            MATCH (c:Company {ticker: $ticker})-[r:SUPPLIES_FROM|SUPPLIES_TO]-(partner:Company)
            RETURN partner.ticker AS ticker, partner.name AS name, type(r) AS relationship
            """,
            ticker=ticker,
        )
