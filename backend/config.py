from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""

    # Voyage AI
    voyage_api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index_name: str = "meridian-financial"
    pinecone_environment: str = "us-east-1-aws"

    # Elasticsearch
    elasticsearch_url: str = "http://localhost:9200"
    elasticsearch_index_name: str = "meridian-chunks"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "meridian_password"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # PostgreSQL
    database_url: str = "postgresql://meridian:meridian@localhost:5432/meridian"

    # SEC EDGAR
    edgar_user_agent: str = "Meridian Research contact@meridian.ai"
    edgar_request_delay: float = 0.1

    # App
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000"]

    # Model routing
    model_simple: str = "claude-haiku-4-5-20251001"
    model_standard: str = "claude-sonnet-4-6"
    model_complex: str = "claude-opus-4-7"

    # Retrieval
    retrieval_top_k: int = 20
    rerank_top_k: int = 8
    embedding_dim: int = 1024  # voyage-finance-2


@lru_cache
def get_settings() -> Settings:
    return Settings()
