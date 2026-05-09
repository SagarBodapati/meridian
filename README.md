# Meridian — Financial Research Copilot

> Advanced agentic RAG system for financial research. Grounded in SEC filings, earnings call transcripts, and real-time financial news.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=flat-square&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-F75C03?style=flat-square&logo=langchain&logoColor=white)
![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6-D97706?style=flat-square&logo=anthropic&logoColor=white)
![Pinecone](https://img.shields.io/badge/Pinecone-Vector%20DB-00B4AB?style=flat-square)
![Elasticsearch](https://img.shields.io/badge/Elasticsearch-8.x-005571?style=flat-square&logo=elasticsearch&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-5.x-008CC1?style=flat-square&logo=neo4j&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)

Meridian goes beyond document retrieval. It reasons across filings, decomposes complex multi-period questions into sub-queries, benchmarks companies side-by-side, and streams structured answers with verifiable citations — all powered by Claude.

---

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Prerequisites](#prerequisites)
5. [Getting API Keys](#getting-api-keys)
6. [Installation](#installation)
7. [Configuration](#configuration)
8. [Running the Project](#running-the-project)
9. [Seeding Data](#seeding-data)
10. [Using the Application](#using-the-application)
11. [API Reference](#api-reference)
12. [Project Structure](#project-structure)
13. [How It Works](#how-it-works)
14. [Evaluation](#evaluation)
15. [Troubleshooting](#troubleshooting)
16. [Cost Reference](#cost-reference)

---

## Features

- **Streaming chat** grounded in SEC filings (10-K, 10-Q, 8-K), earnings call transcripts, and financial news
- **Automatic query routing** — classifies questions and selects the best reasoning path
- **Multi-hop reasoning** — decomposes complex questions (e.g. "how has margin trended over 8 quarters?") into sub-queries, answers each, then synthesizes
- **Comparative analysis** — parallel retrieval across multiple companies with structured side-by-side output
- **Hybrid retrieval** — dense (voyage-finance-2 embeddings) + sparse (BM25) fused via Reciprocal Rank Fusion, then reranked with a cross-encoder
- **HyDE** (Hypothetical Document Embeddings) — improves recall for complex queries
- **Temporal intelligence** — understands "last quarter", "Q3-2024", "past 2 years", and respects fiscal calendars
- **Financial-aware chunking** — tables stored as structured JSON + prose summaries; footnotes linked to parent paragraphs
- **Knowledge graph** — company relationships, competitor sets, executive networks in Neo4j
- **Verifiable citations** — every answer links back to the exact filing section

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 15)                    │
│           Chat · Document Search · Company Analytics             │
└────────────────────────────┬─────────────────────────────────────┘
                             │ SSE streaming
┌────────────────────────────▼─────────────────────────────────────┐
│                     FastAPI Backend (Python 3.12)                │
│                                                                  │
│  POST /chat/stream                                               │
│        │                                                         │
│        ▼                                                         │
│  ┌─────────────┐                                                 │
│  │Query Router │  Claude Haiku — classifies query type          │
│  └──────┬──────┘  + extracts tickers + temporal range           │
│         │                                                        │
│    ┌────┴──────────────────────────┐                            │
│    │                               │                             │
│  simple_factual              multi_hop / trend                  │
│  calculation                 comparative                        │
│    │                         report_generation                   │
│    │                               │                             │
│  ┌─▼───────────┐         ┌────────▼──────────┐                  │
│  │ Simple RAG  │         │  Multi-Hop /      │                  │
│  │   Agent     │         │  Comparative      │                  │
│  └─────────────┘         │  Agent            │                  │
│         │                └────────────────────┘                 │
│         └─────────────┬──────────────────────┘                  │
│                        │                                         │
│              ┌─────────▼──────────┐                             │
│              │  Hybrid Retriever  │                             │
│              │                    │                             │
│              │  1. HyDE query gen │  → voyage-finance-2 embed  │
│              │  2. Dense search   │  → Pinecone (filtered)     │
│              │  3. Sparse search  │  → Elasticsearch BM25      │
│              │  4. RRF fusion     │                             │
│              │  5. Rerank         │  → BGE cross-encoder       │
│              │  6. Temporal decay │                             │
│              └─────────┬──────────┘                             │
│                        │                                         │
│              ┌─────────▼──────────┐                             │
│              │  Claude Sonnet/    │  → streamed answer          │
│              │  Opus generation   │  + citations                │
│              └────────────────────┘                             │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                       KNOWLEDGE LAYER                            │
│   Pinecone · Elasticsearch · Neo4j · TimescaleDB · Redis         │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     INGESTION PIPELINE                           │
│                                                                  │
│  SEC EDGAR (RSS + bulk) → pdfplumber/Camelot (tables) →         │
│  Financial chunker → NER enricher → voyage-finance-2 embed →    │
│  Pinecone upsert + Elasticsearch bulk index                      │
└──────────────────────────────────────────────────────────────────┘
```

### Query routing logic

| Query type | Trigger | Agent | Model |
|------------|---------|-------|-------|
| `simple_factual` | Single fact, one company, one period | SimpleRAGAgent | Sonnet |
| `calculation` | Ratio, yield, growth rate | SimpleRAGAgent | Sonnet |
| `multi_hop` | Cross-document, chain of reasoning | MultiHopAgent | Opus |
| `trend_analysis` | Metric over N periods | MultiHopAgent | Opus |
| `comparative` | Two or more companies | ComparativeAgent | Opus |
| `report_generation` | Comprehensive report requested | MultiHopAgent | Opus |

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| LLM | Claude Haiku 4.5 / Sonnet 4.6 / Opus 4.7 | Classification, Q&A, synthesis |
| Embeddings | `voyage-finance-2` | Financial-domain dense embeddings |
| Vector DB | Pinecone (serverless) | Dense retrieval with metadata filters |
| Sparse search | Elasticsearch 8.x | BM25 keyword retrieval |
| Knowledge graph | Neo4j 5.x (AuraDB) | Company relationships, peer sets |
| Time-series DB | TimescaleDB (PostgreSQL 16) | Financial metrics history |
| Cache / Queue | Redis 7 | Query cache, Celery broker |
| Agent framework | LangGraph 0.2 | Stateful multi-step agent workflows |
| Backend | FastAPI + Python 3.12 | Async API, SSE streaming |
| Frontend | Next.js 15 + TypeScript | Streaming chat UI |
| Styling | Tailwind CSS 3 | UI components |
| Containers | Docker Compose | Local infrastructure |

---

## Prerequisites

Make sure these are installed before starting:

| Tool | Minimum version | Check |
|------|----------------|-------|
| Python | 3.12 | `python --version` |
| pip | 24+ | `pip --version` |
| Node.js | 20 LTS | `node --version` |
| npm | 10+ | `npm --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |

> **macOS**: Install Docker Desktop from docker.com. It includes both Docker and Compose.
> **Linux**: Install `docker-ce` and the `docker-compose-plugin` package.

---

## Getting API Keys

You need **three** external API keys. All have free tiers sufficient for development.

### 1. Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and add a payment method
3. Navigate to **API Keys** → **Create Key**
4. Copy the key — it starts with `sk-ant-`

### 2. Voyage AI API Key (Financial Embeddings)

1. Go to [dash.voyageai.com](https://dash.voyageai.com)
2. Sign up and navigate to **API Keys**
3. Create a new key — it starts with `pa-`
4. The free tier includes 50M tokens/month (enough for development)

> **Why Voyage?** `voyage-finance-2` is trained specifically on financial text (SEC filings, earnings reports). It outperforms OpenAI `text-embedding-3-large` on FinanceBench retrieval by ~12 points on Recall@5.

### 3. Pinecone API Key

1. Go to [app.pinecone.io](https://app.pinecone.io)
2. Sign up (free tier available)
3. Navigate to **API Keys** → copy the default key — it starts with `pcsk_`
4. **Create an index** before running:
   - Name: `meridian-financial`
   - Dimensions: `1024` (voyage-finance-2 output size)
   - Metric: `cosine`
   - Cloud: `AWS` / Region: `us-east-1`

---

## Installation

### Step 1 — Clone / navigate to the project

```bash
cd meridian
```

### Step 2 — Create and activate a Python virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows
```

### Step 3 — Install Python dependencies

```bash
pip install -e ".[dev]"
```

This installs all dependencies declared in `pyproject.toml` including FastAPI, LangGraph, Anthropic SDK, Pinecone, Elasticsearch, Neo4j, Celery, and document processing libraries.

> The first install may take 3–5 minutes due to `unstructured` and `camelot-py` pulling in PDF processing dependencies.

### Step 4 — Download the spaCy NER model

```bash
python -m spacy download en_core_web_lg
```

This is used for named entity recognition (company names, people, dollar amounts) during ingestion enrichment.

### Step 5 — Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Configuration

### Copy the example env file

```bash
cp .env.example .env
```

### Fill in your credentials

Open `.env` and set the following values:

```bash
# ── Required ──────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
VOYAGE_API_KEY=pa-YOUR_KEY_HERE
PINECONE_API_KEY=pcsk_YOUR_KEY_HERE

# ── Pinecone index (must match what you created in the dashboard) ──
PINECONE_INDEX_NAME=meridian-financial
PINECONE_ENVIRONMENT=us-east-1-aws

# ── Infrastructure (auto-configured when using Docker Compose) ────
ELASTICSEARCH_URL=http://localhost:9200
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=meridian_password
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql://meridian:meridian@localhost:5432/meridian

# ── SEC EDGAR (update to your real contact info) ──────────────────
# EDGAR requires a User-Agent with a valid email for API access.
EDGAR_USER_AGENT=YourApp contact@youremail.com

# ── Optional tuning ───────────────────────────────────────────────
ENVIRONMENT=development
LOG_LEVEL=INFO
```

> **EDGAR_USER_AGENT** is required by SEC EDGAR's terms of service. Use a real name and email — EDGAR rate-limits or blocks requests without a proper user agent.

### Full configuration reference

All settings are in [`backend/config.py`](backend/config.py). The complete list:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required. Claude API key |
| `VOYAGE_API_KEY` | — | Required. Voyage AI key |
| `PINECONE_API_KEY` | — | Required. Pinecone key |
| `PINECONE_INDEX_NAME` | `meridian-financial` | Pinecone index name |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | ES endpoint |
| `ELASTICSEARCH_INDEX_NAME` | `meridian-chunks` | ES index name |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `meridian_password` | Neo4j password |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL DSN |
| `EDGAR_USER_AGENT` | `Meridian Research ...` | Required for EDGAR |
| `EDGAR_REQUEST_DELAY` | `0.1` | Seconds between EDGAR requests |
| `MODEL_SIMPLE` | `claude-haiku-4-5-20251001` | Fast classification + HyDE |
| `MODEL_STANDARD` | `claude-sonnet-4-6` | Main Q&A |
| `MODEL_COMPLEX` | `claude-opus-4-7` | Multi-hop, reports |
| `RETRIEVAL_TOP_K` | `20` | Candidates before reranking |
| `RERANK_TOP_K` | `8` | Chunks passed to the LLM |

---

## Running the Project

### Start infrastructure services

```bash
docker compose up redis postgres elasticsearch neo4j -d
```

Wait ~30 seconds for all services to become healthy. You can verify with:

```bash
docker compose ps
# All four services should show "healthy"

# Optional: verify Elasticsearch is up
curl http://localhost:9200/_cluster/health
# Should return: {"status":"green",...}

# Optional: verify Neo4j browser
open http://localhost:7474
# Login: neo4j / meridian_password
```

### Start the backend API

```bash
# From the meridian/ root directory with venv activated
uvicorn backend.main:app --reload --port 8000
```

Expected output:
```
INFO     meridian.startup environment=development
INFO     meridian.db_ready
INFO     meridian.kg_ready
INFO     Application startup complete.
INFO     Uvicorn running on http://0.0.0.0:8000
```

Verify the backend is running:
```bash
curl http://localhost:8000/health
# {"status":"ok","service":"meridian"}
```

Interactive API docs are available at: **http://localhost:8000/docs**

### Start the Celery worker (optional — needed for background ingestion)

```bash
# In a separate terminal, with venv activated
celery -A backend.worker.celery_app worker --loglevel=info --concurrency=4
```

> The Celery worker handles background ingestion jobs. If you don't start it, you can still use the `/ingest/sync` endpoint which runs ingestion inline (blocks the request).

### Start the frontend

```bash
cd frontend
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Seeding Data

The system has no data until you ingest filings. The seed script handles both the knowledge graph (company relationships) and SEC filing ingestion.

### Quick start — 3 companies, 2 years

```bash
python scripts/seed_data.py --tickers AAPL MSFT NVDA --years 2
```

This will:
1. Bootstrap the Neo4j knowledge graph with company metadata and competitor relationships
2. Fetch 10-K and 10-Q filings from SEC EDGAR for each ticker
3. Chunk, enrich, embed, and index into Pinecone + Elasticsearch

Expected time: ~5–15 minutes per company depending on network speed and the number of filings found.

### Seed only the knowledge graph (fast, no API costs)

```bash
python scripts/seed_data.py --tickers AAPL MSFT NVDA GOOGL AMZN --kg-only
```

### Seed only filings (if KG is already populated)

```bash
python scripts/seed_data.py --tickers TSLA --years 3 --filings-only
```

### All default tickers (top 10 S&P 500 companies)

```bash
python scripts/seed_data.py --years 2
# Seeds: AAPL MSFT NVDA GOOGL AMZN META TSLA JPM V UNH
```

> **Tip:** Start with 1–2 tickers and 1 year to verify the full pipeline is working before ingesting large volumes.

### Check ingestion status

```bash
curl http://localhost:8000/api/v1/ingest/status/AAPL | python -m json.tool
```

### Trigger ingestion via API

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "filing_types": ["10-K", "10-Q"], "years_back": 2}'
```

---

## Using the Application

### Chat interface (http://localhost:3000)

The main interface. Type a question in the input box and press Enter or click Send.

**Example questions to try:**

```
What was Apple's revenue in the most recent quarter?
```
→ Routes to `simple_factual` · Uses SimpleRAG · Returns in ~2s

```
How has Apple's services gross margin trended over the last 8 quarters?
```
→ Routes to `trend_analysis` · Uses MultiHop (decomposes into 4 sub-queries) · Streams step-by-step reasoning

```
Compare NVIDIA and AMD gross margins in 2024
```
→ Routes to `comparative` · Parallel retrieval for NVDA + AMD · Returns structured comparison table

```
Generate a research report on Microsoft's cloud business
```
→ Routes to `report_generation` · Full Opus-powered report with MD&A, financials, risks, and guidance

**Filter by ticker:** Use the ticker input above the chat box to constrain retrieval to a single company. Leave blank to search across all indexed companies.

### Document Search (http://localhost:3000/search)

Direct semantic + keyword search across all indexed chunks. Useful for:
- Finding specific passages in filings
- Verifying what data has been indexed
- Debugging retrieval quality

### Company Analytics (http://localhost:3000/analytics)

Knowledge graph view for any indexed company. Shows:
- Leadership team (executives from the KG)
- Peer set (same-sector companies)
- Competitor relationships
- Recent financial news (live from RSS feeds)

---

## API Reference

All endpoints are prefixed with `/api/v1`. Full interactive docs at `http://localhost:8000/docs`.

### Chat

#### `POST /api/v1/chat/stream`

Server-Sent Events streaming endpoint. Returns a stream of JSON events.

**Request:**
```json
{
  "message": "What was Apple's gross margin in Q3 2024?",
  "session_id": "optional-uuid-for-conversation-history",
  "history": [],
  "filters": { "ticker": "AAPL" }
}
```

**Stream events:**
```
event: token
data: {"type": "token", "text": "Apple's"}

event: token
data: {"type": "token", "text": " gross margin..."}

event: citations
data: {"type": "citations", "citations": [{"source": "Apple 10-Q Q3-2024", ...}]}

event: done
data: {"type": "done", "session_id": "...", "query_type": "simple_factual", "latency_ms": 1842}
```

#### `POST /api/v1/chat`

Non-streaming — waits for the full answer. Useful for programmatic use.

**Response:**
```json
{
  "session_id": "abc123",
  "answer": "Apple's gross margin in Q3 2024 was 46.3%...",
  "citations": [...],
  "query_type": "simple_factual",
  "retrieved_chunks": 8,
  "latency_ms": 2100,
  "model_used": "claude-sonnet-4-6"
}
```

### Ingestion

#### `POST /api/v1/ingest`

Queue background ingestion (returns immediately).

```json
{ "ticker": "AAPL", "filing_types": ["10-K", "10-Q"], "years_back": 3 }
```

#### `POST /api/v1/ingest/sync`

Synchronous ingestion (waits for completion). Use for small jobs or testing.

#### `GET /api/v1/ingest/status/{ticker}`

Returns ingestion log with status per filing period.

#### `DELETE /api/v1/ingest/{ticker}`

Removes all indexed data for a ticker from Pinecone, Elasticsearch, and the ingestion log.

### Search

#### `POST /api/v1/search`

Direct hybrid chunk retrieval — bypasses agents.

```json
{
  "query": "services revenue guidance",
  "ticker": "AAPL",
  "filing_type": "10-Q",
  "top_k": 10
}
```

### Reports

#### `GET /api/v1/reports/company/{ticker}`

Knowledge graph profile + live news for a company.

#### `POST /api/v1/reports/generate?ticker=AAPL&period=Q3-2024`

Generate a full research report (long-running, ~30–60s for Opus).

#### `GET /api/v1/reports/metrics/{ticker}?periods=8`

Financial metrics time series from the metric store.

---

## Project Structure

```
meridian/
│
├── backend/                          # FastAPI application
│   ├── main.py                       # App factory + lifespan (DB/KG init)
│   ├── config.py                     # Pydantic settings (reads .env)
│   ├── database.py                   # TimescaleDB schema + asyncpg pool
│   ├── worker.py                     # Celery task definitions
│   │
│   ├── models/                       # Pydantic data models
│   │   ├── documents.py              # DocumentChunk, ChunkMetadata, FilingType
│   │   ├── queries.py                # ChatRequest/Response, Citation, SearchRequest
│   │   └── financial.py             # FinancialMetric, Company, EarningsEstimate
│   │
│   ├── ingestion/                    # Data ingestion pipeline
│   │   ├── edgar.py                  # Async SEC EDGAR client (RSS + bulk API)
│   │   ├── chunker.py                # Financial-aware chunker (narrative/table/footnote)
│   │   ├── enricher.py               # NER, sentiment, metric flag enrichment
│   │   ├── indexer.py                # VoyageEmbedder, PineconeIndexer, ElasticsearchIndexer
│   │   └── processor.py             # Pipeline orchestrator (fetch→chunk→enrich→index)
│   │
│   ├── retrieval/                    # Retrieval engine
│   │   ├── hybrid.py                 # RRF fusion of dense + sparse results
│   │   ├── hyde.py                   # Hypothetical Document Embedding query expansion
│   │   ├── reranker.py               # BGE cross-encoder + temporal decay scoring
│   │   └── temporal.py              # Parse relative dates → DateFilter → Pinecone/ES filters
│   │
│   ├── agents/                       # LangGraph agentic layer
│   │   ├── state.py                  # AgentState (shared Pydantic model for all nodes)
│   │   ├── router.py                 # Query classifier → route decision
│   │   ├── prompts.py                # All system + user prompt templates
│   │   ├── simple_rag.py             # Single-pass retrieval + generation + streaming
│   │   ├── multi_hop.py             # Decompose → parallel retrieve → synthesize
│   │   ├── comparative.py           # Parallel per-company retrieval + comparison
│   │   └── graph.py                  # LangGraph StateGraph definition + MeridianGraph class
│   │
│   ├── tools/                        # Financial computation tools
│   │   ├── calculator.py             # Ratios, YoY/CAGR, margins, FCF, DSO, etc.
│   │   ├── charts.py                 # Plotly-spec generators (line, bar, waterfall, multi-series)
│   │   └── news.py                   # RSS news aggregator + keyword filter
│   │
│   ├── knowledge_graph/
│   │   └── client.py                 # Neo4j driver wrapper + Cypher queries
│   │
│   └── api/routes/
│       ├── chat.py                   # SSE streaming + non-streaming chat endpoints
│       ├── ingest.py                 # Trigger/status/delete ingestion
│       ├── search.py                 # Direct hybrid search endpoint
│       └── reports.py               # Company profile, report generation, metrics
│
├── frontend/                         # Next.js 15 application
│   └── src/
│       ├── app/
│       │   ├── page.tsx              # Main chat page
│       │   ├── search/page.tsx       # Document search page
│       │   └── analytics/page.tsx   # Company analytics page
│       ├── components/
│       │   ├── Chat/
│       │   │   ├── ChatWindow.tsx    # Main chat interface + example queries
│       │   │   ├── Message.tsx       # Message bubble with markdown rendering
│       │   │   ├── Citations.tsx     # Collapsible citation cards with source links
│       │   │   └── QueryTypeBadge.tsx # Colored badge per query type
│       │   ├── Research/
│       │   │   └── IngestPanel.tsx   # Sidebar ingest form
│       │   └── Sidebar.tsx           # Navigation + ingest panel
│       ├── hooks/
│       │   └── useChat.ts            # SSE streaming hook with optimistic UI
│       └── lib/
│           ├── api.ts                # Backend API client (fetch + SSE parser)
│           ├── types.ts              # TypeScript interfaces
│           └── utils.ts              # cn() tailwind utility
│
├── scripts/
│   └── seed_data.py                  # Bootstrap KG + ingest top companies
│
├── evals/
│   └── eval_runner.py                # Keyword accuracy + latency evaluation harness
│
├── docker-compose.yml                # Redis, Postgres, Elasticsearch, Neo4j
├── Dockerfile                        # Backend container image
├── pyproject.toml                    # Python dependencies + build config
└── .env.example                      # Environment variable template
```

---

## How It Works

### Ingestion pipeline

1. **EDGAR fetch** — `edgar.py` polls SEC EDGAR's full-text search API and RSS feed for 10-K/10-Q/8-K filings. Retries with exponential backoff, respects the 10 req/s EDGAR rate limit.

2. **Financial chunking** — `chunker.py` splits filing text with awareness of:
   - HTML tables: extracted with a lightweight parser, stored as JSON *and* as a prose summary (e.g. "Apple Q3 2024 revenue was $85.8B, up from $81.8B in Q3 2023 (+4.9% YoY)")
   - MD&A section: paragraph-level chunks for higher granularity
   - Footnotes: detected by `(1)` patterns, stored as separate chunks
   - Narrative text: sentence-boundary chunks with 64-token overlap

3. **Metadata enrichment** — every chunk gets: financial metric presence flag, guidance flag, simple sentiment score, and spaCy NER entities.

4. **Multi-level indexing** — each chunk is embedded with `voyage-finance-2` and upserted to Pinecone with rich metadata (ticker, filing type, fiscal period, section, report date timestamp). The full text is also bulk-indexed into Elasticsearch for BM25 retrieval.

### Retrieval pipeline

1. **Temporal resolution** — the query is parsed for date references before retrieval. "Last quarter" resolves to the correct date range; "Q3-2024" constrains the Pinecone metadata filter directly.

2. **HyDE** — a hypothetical answer passage is generated by Claude Haiku, then both the query and the hypothetical document are embedded. The averaged vector bridges the vocabulary gap between short queries and long-form filing text.

3. **Dual retrieval** — dense (Pinecone top-20) and sparse (ES BM25 top-20) run in parallel. Results are fused with RRF (Reciprocal Rank Fusion), which reliably outperforms either alone on recall.

4. **Reranking** — the BGE cross-encoder (`BAAI/bge-reranker-v2-m3`) scores each (query, chunk) pair. A temporal decay factor `score × e^(-λ × days_old)` biases toward recent filings without hard cutoffs.

5. **Hydration** — Pinecone stores a 200-char text preview in metadata. Before generation, chunks are hydrated with their full text from Elasticsearch.

### Agent routing

The `QueryRouter` calls Claude Haiku to classify the query into one of 6 types, extract tickers, and determine temporal scope — all in one fast call under 300ms. A regex fallback catches failures.

- **SimpleRAGAgent**: builds context from top-8 reranked chunks, calls Claude Sonnet with a factual Q&A system prompt, streams the response.
- **MultiHopAgent**: calls Claude Sonnet to decompose the question into 2–4 sub-questions, runs SimpleRAGAgent for each in sequence, then calls Claude Opus to synthesize a final answer.
- **ComparativeAgent**: runs retrieval for each ticker in parallel (`asyncio.gather`), concatenates per-company contexts, and calls Claude Opus with a structured comparison system prompt.

---

## Evaluation

Run the built-in evaluation suite against any indexed companies:

```bash
# Runs 6 sample questions and measures keyword recall + latency
python evals/eval_runner.py
```

Sample output:
```
[1/6] What was Apple's total revenue in the most recent fiscal quarter?...
  ✓ PASS | latency: 2341ms | chunks: 8 | citations: 3

[2/6] What are the main risk factors Apple disclosed in its most recent 10-K?...
  ✓ PASS | latency: 3102ms | chunks: 8 | citations: 5

====================================================
EVALUATION SUMMARY
====================================================
  total: 6
  passed: 5
  failed: 1
  pass_rate: 83.3%
  avg_latency_ms: 2890
  avg_chunks_retrieved: 7
  avg_citations: 4
```

### Custom evaluation set

Create a JSON file:
```json
[
  {
    "question": "What was NVDA's data center revenue in Q4 FY2024?",
    "ticker": "NVDA",
    "expected_keywords": ["data center", "revenue", "billion"],
    "expected_number": null,
    "expected_period": "Q4",
    "category": "factual"
  }
]
```

Run it:
```bash
python evals/eval_runner.py --questions my_questions.json --output evals/my_results.json
```

### Target metrics (FinanceBench)

| Metric | Target | Measurement method |
|--------|--------|-------------------|
| Retrieval Recall@5 | >88% | Gold chunk in top-5 reranked results |
| Answer numerical accuracy | >95% | Auto-verify against XBRL data |
| Citation precision | >92% | Cited chunk actually contains the claim |
| Hallucination rate | <3% | LLM-as-judge spot check |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'backend'`

Make sure you installed in editable mode from the project root with the venv active:
```bash
# From meridian/ with .venv activated
pip install -e .
```

### Pinecone `NotFoundException` — index not found

You must create the index manually in the Pinecone dashboard *before* running ingestion:
- Name: `meridian-financial`
- Dimensions: **1024** (voyage-finance-2 output)
- Metric: `cosine`

### Elasticsearch connection refused

The Docker container may not have finished starting. Wait ~15s and check:
```bash
docker compose ps elasticsearch
curl http://localhost:9200/_cluster/health
```

### EDGAR returns empty results

1. Verify your `EDGAR_USER_AGENT` is set to a real email address in `.env`
2. Check EDGAR's status at [efts.sec.gov](https://efts.sec.gov/LATEST/search-index?q=%22AAPL%22&forms=10-Q)
3. Some tickers have different EDGAR entity names — try the company's legal name

### spaCy model not found (`[E050]`)

```bash
python -m spacy download en_core_web_lg
```

### Neo4j authentication failed

The default password in `docker-compose.yml` is `meridian_password`. If you changed it, update `NEO4J_PASSWORD` in `.env`.

### Frontend `uuid` not found

```bash
cd frontend && npm install uuid @types/uuid
```

### Celery worker crashes immediately

Make sure Redis is running and `REDIS_URL` in `.env` points to it:
```bash
docker compose up redis -d
redis-cli ping  # should return PONG
```

---

## Cost Reference

Approximate costs at moderate usage (10 queries/day during development):

| Service | Free tier | Paid estimate |
|---------|-----------|---------------|
| Anthropic (Claude) | $5 free credit | ~$5–20/month at dev scale |
| Voyage AI | 50M tokens/month free | Free for development |
| Pinecone | 2GB storage free | Free for ≤1M vectors |
| All infra (Redis, ES, Neo4j, Postgres) | Docker (free locally) | — |

For production at scale (~10K queries/day), see the [implementation plan's cost model](https://github.com) for a ~$4,000/month estimate with prompt caching cutting 40–60% off LLM costs.

**To minimize costs during development:**
- Use `MODEL_COMPLEX=claude-sonnet-4-6` instead of Opus in `.env` (Sonnet is ~5x cheaper)
- Limit seed data: `--tickers AAPL --years 1` (fewer chunks = fewer embedding API calls)
- Use `/ingest/sync` and watch logs to confirm each step completes before adding more tickers

---

## Running Everything at Once (cheat sheet)

```bash
# Terminal 1 — infrastructure
cd meridian
docker compose up redis postgres elasticsearch neo4j -d

# Terminal 2 — backend
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 3 — celery worker (optional)
source .venv/bin/activate
celery -A backend.worker.celery_app worker --loglevel=info

# Terminal 4 — frontend
cd frontend
npm run dev

# Terminal 5 — seed data (one-time)
source .venv/bin/activate
python scripts/seed_data.py --tickers AAPL MSFT --years 1
```

Then open **http://localhost:3000** and ask:

> *"How has Apple's gross margin trended over the last 4 quarters?"*
