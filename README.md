# DarkAtlas Asset Management API
### AI-powered Attack Surface Monitoring — Track B (AI Applications)

---
## Overview

DarkAtlas Asset Management API is a security-focused asset tracking system 
built for Buguard's Attack Surface Monitoring platform. It ingests, deduplicates, 
and lifecycle-manages an organization's internet-facing assets — domains, subdomains, 
IP addresses, services, TLS certificates, and technologies — while exposing a 
LangChain-powered AI layer for natural-language querying, risk scoring, enrichment, 
and report generation.
---

## Quick Start

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd darkatlas-ai
```

### 2. Create your `.env` file
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```
GROQ_API_KEY=gsk_your_actual_key_here
TAVILY_API_KEY=tvly_your_actual_key_here
DATABASE_URL=postgresql://postgres:postgres@db:5432/darkatlas
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=darkatlas
```

### 3. Run with Docker
```bash
docker-compose up --build
```

### 4. Open API docs
```
http://localhost:8000/docs
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (starts with `gsk_`) |
| `TAVILY_API_KEY` | Tavily API key for agent web search (starts with `tvly_`) |
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_USER` | Postgres username |
| `POSTGRES_PASSWORD` | Postgres password |
| `POSTGRES_DB` | Postgres database name |

---

## API Endpoints

### Import
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/import` | Bulk import assets from JSON array |

### Assets
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/assets` | List assets with filtering + pagination |
| GET | `/api/v1/assets/{id}` | Get single asset by ID |

### Analyze (AI Features)
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/analyze` | Run AI analysis — 5 modes including agent |

---

## AI Analysis Modes

### Mode 1 — `nl_query` (Natural Language Query)

**Request:**
```json
{
  "mode": "nl_query",
  "input": "show me all expired certificates on production subdomains"
}
```

**Response:**
```json
{
  "question": "show me all expired certificates on production subdomains",
  "filters_used": { "type": "certificate", "status": null, "tags": ["prod"], "value_contains": null },
  "count": 1,
  "results": [
    { "id": "a3", "type": "certificate", "value": "cn=api.example.com", "status": "active" }
  ]
}
```

---

### Mode 2 — `risk_score` (Risk Scoring & Summarization)

**Request (all assets):**
```json
{ "mode": "risk_score" }
```

**Request (single asset):**
```json
{ "mode": "risk_score", "asset_id": "a3" }
```

**Response:**
```json
{
  "risk_score": 78,
  "risk_level": "high",
  "findings": [
    {
      "issue": "Certificate cn=api.example.com expired on 2025-01-02",
      "severity": "critical",
      "affected_assets": ["cn=api.example.com"]
    }
  ],
  "summary": "The asset inventory contains 1 expired certificate posing immediate risk.",
  "recommendations": [
    "Renew expired certificate for api.example.com immediately",
    "Set up automated certificate renewal"
  ]
}
```

---

### Mode 3 — `enrich` (Enrichment & Categorization)

**Request:**
```json
{ "mode": "enrich", "asset_id": "a2" }
```

**Response:**
```json
{
  "asset_id": "a2",
  "enrichment": {
    "environment": "prod",
    "category": "api",
    "criticality": "high",
    "suggested_tags": ["prod", "api", "external"],
    "reasoning": "Value contains 'api' and no staging/dev indicators"
  },
  "updated_tags": ["prod", "api", "external"],
  "updated_metadata": {
    "environment": "prod",
    "category": "api",
    "criticality": "high",
    "enriched_at": "2025-06-27T10:00:00+00:00"
  }
}
```

---

### Mode 4 — `report` (Natural Language Report Generation)

**Request:**
```json
{ "mode": "report", "filters": {} }
```

**Response:**
```json
{
  "total_assets": 10,
  "by_type": { "domain": 2, "subdomain": 3, "certificate": 3, "service": 2 },
  "by_status": { "active": 8, "stale": 2 },
  "report": "## Executive Summary\n\nThe organization's attack surface consists of 10 assets..."
}
```

---

### Mode 5 — `agent` (Agentic Tool-Use with Tavily)

The agent autonomously:
1. Searches internal DB for matching assets
2. Searches Tavily for real-world CVEs and threat intelligence
3. Combines both to give an enriched security answer

**Request:**
```json
{
  "mode": "agent",
  "input": "Are there any known vulnerabilities related to the certificates in our database?"
}
```

**Response:**
```json
{
  "question": "Are there any known vulnerabilities related to the certificates in our database?",
  "answer": "The internal database contains 2 certificates issued by Let's Encrypt. According to recent threat intelligence from Tavily, there are no active CVEs targeting Let's Encrypt certificates directly. However, the certificate cn=api.example.com expired on 2025-01-02, making it immediately exploitable for MITM attacks. Recommendation: renew immediately.",
  "steps_taken": [
    {
      "tool": "search_assets",
      "input": "certificate",
      "output": "[{\"id\": \"a3\", \"type\": \"certificate\", ...}]"
    },
    {
      "tool": "tavily_search",
      "input": "Let's Encrypt certificate vulnerabilities CVE 2025",
      "output": "No critical CVEs found for Let's Encrypt in 2025..."
    }
  ],
  "total_steps": 2
}
```

---

## Running Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

Tests use SQLite (no Docker needed) and mock LLM calls so they run fast and offline.

---

## Design Decisions & Assumptions

### Deduplication
- Dedup key: `(type, value)` — same type + same normalized value = same asset
- `value` is normalized to lowercase on ingest
- `first_seen` is never overwritten
- `last_seen` is always updated on re-import
- `tags` are merged (union — existing tags are never dropped)
- `metadata` is deep-merged; incoming values win on conflict
- A `stale` asset that reappears is automatically set back to `active`

### Hallucination Prevention
- The LLM never returns asset data directly to the user
- `nl_query`: LLM produces filters only → applied to real DB → real data returned
- `risk_score` / `report`: real assets passed to LLM as context with strict grounding instructions
- `agent`: DB tool always called first; Tavily only used for external enrichment

### Bulk Import
- Each record processed independently — one bad record never fails the whole batch
- Response always includes `imported`, `updated`, `failed`, and `errors`

### Agent Design
- Built with LangChain `create_tool_calling_agent`
- Two tools: `search_assets` (internal DB) + `TavilySearchResults` (internet)
- Max 5 iterations to prevent infinite loops
- Returns intermediate steps so the user can see the agent's reasoning

### What I Would Add With More Time
- Alembic migrations instead of `create_all`
- Relationship endpoints (asset graph traversal)
- Redis caching for repeated LLM calls
- Rate limiting on `/analyze`
- Multi-tenant organization isolation
- Background task for marking stale assets (last_seen > 30 days)
- CI pipeline with GitHub Actions

---

## Project Structure

```
darkatlas-ai/
├── app/
│   ├── main.py
│   ├── models/
│   │   ├── asset.py                # SQLAlchemy models
│   │   └── schemas.py              # Pydantic schemas
│   ├── api/routes/
│   │   ├── import_route.py         # POST /import
│   │   ├── assets_route.py         # GET /assets
│   │   └── analyze_route.py        # POST /analyze (5 modes)
│   ├── db/
│   │   └── database.py
│   └── ai/
│       ├── agent/
│       │   └── darkatlas_agent.py  #  Agent (DB + Tavily)
│       ├── chains/
│       │   ├── nl_query.py         # Feature 1
│       │   ├── risk_scoring.py     # Feature 2
│       │   ├── enrichment.py       # Feature 3
│       │   └── report_gen.py       # Feature 4
│       └── prompts/
│           ├── nl_query_prompt.py
│           ├── risk_prompt.py
│           ├── enrichment_prompt.py
│           └── report_prompt.py
├── tests/
│   ├── test_import.py
│   └── test_analyze.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---


