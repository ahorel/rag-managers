# MatchConsult — Technical Architecture

**Version:** 2.5 (branch `ovh-rag-managers`, commit `464cdb8`)
**Context:** AI-powered consultant matching platform built for Orange Business ESN sourcing.
Automatically matches a client need (free-text expression, email, job description) against a pool
of consultant CVs and ranks candidates by relevance.

---

## 1. High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          OVH VPS — 51.83.44.48                          │
│                                                                          │
│   ┌──────────────┐    ┌──────────────────┐    ┌──────────────────────┐  │
│   │   Frontend   │    │     Backend      │    │       Qdrant         │  │
│   │  React/Vite  │◄──►│  FastAPI Python  │◄──►│  Vector Database     │  │
│   │  Port :80    │    │   Port :8000     │    │   Port :6333         │  │
│   └──────────────┘    └────────┬─────────┘    └──────────────────────┘  │
│                                │                                         │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │ HTTPS
                    ┌────────────▼────────────┐
                    │      External LLMs       │
                    │  Groq (primary)          │
                    │  Anthropic (fallback)    │
                    └─────────────────────────┘
```

The entire stack runs in **Docker Compose** on a single VPS. All services are containerised and
communicate over an internal Docker network.

---

## 2. Infrastructure

| Component | Technology | Details |
|---|---|---|
| Server | OVH VPS | Ubuntu 22.04, 4 vCPU, 8 GB RAM |
| Orchestration | Docker Compose | 4 services : qdrant, backend, frontend, tests |
| Frontend | Nginx | Serves the React build, reverse-proxies API calls |
| Backend | Uvicorn | 2 workers, ASGI, FastAPI |
| Vector DB | Qdrant | In-memory + disk persistence via Docker volume |
| CV storage | Docker volume | PDF/DOCX files mounted at `backend/data/cvs/` |

### Docker Compose services

```yaml
services:
  qdrant     → vector database, port 6333
  backend    → FastAPI + ML model, port 8000, healthcheck
  frontend   → React/Nginx, port 80
  tests      → test runner (profile "test", starts after backend is healthy)
```

---

## 3. Technology Stack

### Backend

| Layer | Technology | Version |
|---|---|---|
| Framework | FastAPI | 0.110+ |
| Runtime | Python | 3.12 |
| ML embeddings | sentence-transformers | paraphrase-multilingual-MiniLM-L12-v2 |
| Vector search | qdrant-client | Latest |
| PDF parsing | pdfplumber | Latest |
| DOCX parsing | python-docx | Latest |
| Data validation | Pydantic v2 | 2.x |
| Config | pydantic-settings | via .env file |
| Primary LLM | Groq API | llama-3.1-8b-instant |
| Fallback LLM | Anthropic API | claude-sonnet-4-6 / claude-haiku-4-5 |

### Frontend

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build tool | Vite |
| HTTP client | Axios |
| Styling | Tailwind CSS |
| Container | Nginx (Alpine) |

---

## 4. Core RAG Pipeline

RAG stands for **Retrieval-Augmented Generation**. MatchConsult uses it to find the most
semantically relevant CVs for a given client need, then uses an LLM to explain the match.

```
User input (free text)
        │
        ▼
┌───────────────────┐
│  LLM Rewrite      │  Groq llama-3.1-8b-instant
│  (claude_service) │  Structures the free text into a typed offer:
└────────┬──────────┘  title, skills, domain, location, duration…
         │
         ├─── Structured offer  ──────────────────────────────────►  Keyword matching
         │                                                            (post-scoring)
         │
         ▼  Raw user text (not the enriched offer)
┌───────────────────┐
│  Embedding        │  paraphrase-multilingual-MiniLM-L12-v2
│  (embeddings.py)  │  384-dimensional vector, multilingual
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  Qdrant Search    │  Cosine similarity, top-50 results
│  + Native Filter  │  Pre-filters: status (intercontrat), languages
└────────┬──────────┘
         │  50 candidate CVs with raw cosine scores
         ▼
┌───────────────────┐
│  Hybrid Scoring   │  Python post-processing (matcher.py)
│  (matcher.py)     │  4 components → final % score
└────────┬──────────┘
         │
         ▼
┌───────────────────┐
│  LLM Explanation  │  Groq llama-3.1-8b-instant (parallel calls)
│  (claude_service) │  One sentence per consultant explaining the match
└────────┬──────────┘
         │
         ▼
      JSON response → Frontend
```

---

## 5. Embedding Model

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers / HuggingFace)

- 384-dimensional float32 vectors
- Supports 50+ languages including French
- Model size: ~120 MB, loaded once at startup
- Max input: 512 tokens (~350–400 words)
- Distance metric: Cosine similarity

**CV indexing:** At startup, every CV file is parsed, truncated to 6,000 characters, and encoded
into a 384-dim vector. Each vector is stored in Qdrant alongside a metadata payload (name,
availability status, domains, location, years of experience…).

**Cosine calibration:** The model produces scores in the practical range 0.25–0.85 on real
documents (never reaches theoretical 1.0 on long texts). Raw scores are normalised to [0, 1]
using a linear calibration formula before entering the scoring system.

---

## 6. Scoring System

The final score displayed to the user is **not** the raw cosine similarity. It is a composite
score built from 4 to 5 components, normalised against the maximum achievable for the active
criteria of that specific query.

### Components

| Component | Max points | Condition |
|---|---|---|
| **Skills** | 55 | Always active |
| **Domain** | 25 | Only if domain is specified or inferred by LLM |
| **Availability** | 15 | Always active |
| **Location** | 5 | Only if location or remote preference is specified |
| **Seniority** | 5 | Only if seniority level detected in the request |

### Skills score (hybrid)

```
calibrated_cosine = (raw_cosine - 0.25) / (0.85 - 0.25)    → [0.0 – 1.0]
keyword_ratio     = skills found literally in CV / total skills
hybrid            = calibrated_cosine × 0.70 + keyword_ratio × 0.30
skills_score      = round(hybrid × 55)                       → [0 – 55 pts]
```

The 70/30 split prevents embedding dilution on senior CVs with rich, varied content: a consultant
with "Java" mentioned 15 times is rewarded over someone with a generically similar embedding.

### Availability score

| Status | Score |
|---|---|
| `intercontrat` (available now) | 15 pts |
| `preavailable` (known end date soon) | 7 pts |
| `en_mission` with end date ≤ 30 days | 5 pts |
| `en_mission` with end date ≤ 90 days | 2 pts |
| `en_mission` without known end date | 3 pts (neutral minimum) |

### Seniority score

Detected from the request ("sénior", "expert", "junior"…) and matched against years of experience
extracted from the CV text (regex: "X ans d'expérience").

| Request \ CV level | Expert (12+ yrs) | Senior (6–11 yrs) | Confirmed (3–5 yrs) | Junior (<3 yrs) |
|---|---|---|---|---|
| **expert** | 5 | 2 | 0 | 0 |
| **senior** | 3 | 5 | 1 | 0 |
| **junior** | 0 | 0 | 1 | 5 |

### Adaptive denominator

```
max_possible = 55 (skills)
             + 25 (if domain active)
             + 5  (if location/remote active)
             + 15 (availability, always)
             + 5  (if seniority detected)

display_score = min(100, round(raw_total × 100 / max_possible))
```

This ensures that a query without domain/location does not artificially cap all scores at 70%.

---

## 7. LLM Integration

### Primary: Groq API

- Model: `llama-3.1-8b-instant`
- Used for: offer rewriting (structured JSON extraction) + match explanations
- Latency: ~3–8 seconds per call
- On failure: automatic retry after 3 seconds

### Fallback: Anthropic API

- Offer rewriting: `claude-sonnet-4-6`
- Match explanations: `claude-haiku-4-5`
- Activated automatically if Groq key is absent or if Groq fails twice

### Final fallback: graceful degradation

If both LLMs fail twice, the system continues with the raw mission text as the offer and skips
LLM-generated explanations. The matching still works (embeddings + keyword scoring). No HTTP 500
is returned to the user.

---

## 8. CV Parsing

**Supported formats:** PDF, DOCX, DOC

| Format | Library | Method |
|---|---|---|
| PDF | pdfplumber | Page-by-page text extraction |
| DOCX/DOC | python-docx | Paragraph extraction |

The full extracted text is stored in the Qdrant payload for keyword matching. Only the first
6,000 characters are passed to the embedding model (model token limit).

---

## 9. Consultant Metadata

Consultant data not present in the CV itself (availability, business domains, location, remote
preferences, email) is stored in a manually maintained JSON file:

**`backend/data/consultants_meta.json`**

```json
{
  "cv_filename_without_extension": {
    "name": "First LAST",
    "title": "Senior Java Developer",
    "status": "intercontrat | preavailable | en_mission",
    "availability_date": "2026-09-01",
    "location": "Paris",
    "remote": "full | partial | none",
    "languages": ["fr", "en"],
    "domains": ["finance", "telecom"],
    "email": "consultant@email.com"
  }
}
```

Domains currently supported: `industrie`, `telecom`, `innovation`, `mobilite`, `finance`,
`assurance`. The system knows that `finance ↔ assurance` and `telecom ↔ innovation` are
semantically close (partial domain score applied to adjacent domains).

---

## 10. API Endpoints

Base URL: `http://51.83.44.48:8000/api`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Backend status: model loaded, CV count |
| `POST` | `/analyze` | Main matching endpoint |
| `POST` | `/send-results` | Email shortlisted consultants |
| `GET` | `/config/admin` | Read app + email config (keys masked) |
| `PUT` | `/config/admin` | Update LLM keys, SMTP config |
| `GET` | `/domains` | List of available business domains |
| `GET` | `/cvs/{filename}` | Serve a CV file |

### POST /analyze — request body

```json
{
  "mission_text": "string (min 20 chars)",
  "filter_domain": "finance | telecom | ...",
  "filter_location": "Paris",
  "filter_remote": "full | partial | none",
  "filter_languages": ["fr", "en"],
  "filter_intercontrat_only": false,
  "priority_skills": ["Java", "Spring Boot"],
  "max_results": 10
}
```

### POST /analyze — response

```json
{
  "rewritten_offer": {
    "title": "...", "technical_skills": [...], "domain": "...", ...
  },
  "consultants": [
    {
      "name": "...", "score": 89, "status": "intercontrat",
      "matched_skills": ["Java", "Spring Boot"],
      "missing_skills": ["JUnit"],
      "explanation": "...",
      "score_detail": { "skills": 47, "domain": 0, "availability": 15, "location": 0 }
    }
  ],
  "total_cvs": 25
}
```

---

## 11. Automated Test Suite

A Docker service (`python:3.12-slim`, profile `test`) starts after the backend passes its
healthcheck and runs **9 integration scenarios**:

| Scenario | What is tested |
|---|---|
| S01a | Simple query: "développeur java sénior" → Java in skills, Java devs in top 3 |
| S01b | Full expression: Java + Spring Boot + Maven + JUnit |
| S02 | MOA project manager, domain filter: finance |
| S03 | Product Owner Agile, HTTP 200, correct mission_type extraction |
| S04 | `filter_intercontrat_only=true` → no `en_mission` in results |
| S05 | Network architect, domain filter: telecom |
| S06 | Multi-criteria: domain + location + remote + language |
| S07 | Robustness: text < 20 chars → HTTP 422 |
| S08 | Stability: same query twice → consistent ranking |

Results are saved as `tests/results/report_YYYYMMDD_HHMMSS.json` and emailed as an HTML report
with JSON attachment to the configured recipients.

**Current score: 8/9** (S04 occasionally shows non-deterministic LLM behaviour on domain field).

Launch command:
```bash
docker compose --profile test run --rm tests
```

---

## 12. Security & Secrets Management

| Secret | Storage |
|---|---|
| Groq API key | `.env` file on server (gitignored), Docker env var |
| Anthropic API key | `.env` file on server (gitignored) |
| SMTP credentials | `.env` file on server (gitignored) |
| Server SSH password | `SERVEUR_ACCES.txt` locally (gitignored) |
| CV files | `backend/data/cvs/` (gitignored — personal data) |
| Client briefs | `backend/data/ao_clients/` (gitignored — confidential) |

No secrets are committed to the repository. The `.env` file is manually created on the server
and populated with production keys.

---

## 13. Deployment Flow

```bash
# Local machine — push changes
git push origin ovh-rag-managers

# On the OVH server
ssh ubuntu@51.83.44.48
cd ~/rag-managers
git pull
docker compose down
docker compose up -d --build      # full rebuild required when CV payload or model changes
```

The backend healthcheck waits up to 120 seconds for the ML model to load and all CVs to be
indexed before accepting traffic. The frontend and test containers depend on `service_healthy`.

---

## 14. Roadmap — V3 Improvements (identified, not yet implemented)

| Improvement | Impact | Description |
|---|---|---|
| **CV chunking** | High | Index N vectors per CV (512-token sliding window) instead of 1. Prevents expertise dilution for senior profiles with long, varied CVs. |
| **Incremental Qdrant index** | Medium | Only re-index CVs that changed since last startup (MD5 diff), instead of full rebuild each time. Reduces startup time from ~60s to <5s with 200+ CVs. |
| **Advanced seniority parsing** | Medium | Count mission date ranges in CVs to compute total years, instead of relying on regex on free text. |

---

*Document generated 2026-06-12 — MatchConsult v2.5*
