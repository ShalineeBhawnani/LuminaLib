# 📚 LuminaLib — Intelligent Library System

> A production-grade, AI-powered library API built with FastAPI, PostgreSQL, Llama 3 (Ollama), and Docker.

---

## ✨ Features

| Domain | Capability |
|--------|-----------|
| **Auth** | JWT signup/login, bcrypt passwords, profile management |
| **Books** | File upload (PDF/TXT), full CRUD, pagination, borrow/return mechanics |
| **GenAI** | Async book summarization + rolling review consensus via Llama 3 |
| **Reviews** | Borrow-gated submissions, per-review sentiment classification |
| **ML** | Content-based & collaborative filtering recommendations |
| **Infra** | Fully Dockerized; swap LLM/storage with one env var change |

---

## 🚀 Quick Start (One Command)

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20
- 8 GB RAM recommended (Llama 3 model is ~4.7 GB)

### 1. Clone & Configure

```bash
git clone https://github.com/ShalineeBhawnani/LuminaLib
cd luminalib

# Copy the environment template
cp .env.example .env

# ⚠️  Generate a secure JWT secret key:
openssl rand -hex 32
# Paste the output into .env as SECRET_KEY
```

### 2. Start Everything

```bash
docker-compose up --build
```

This single command starts:
| Container | Role | Port |
|-----------|------|------|
| `luminalib_db` | PostgreSQL 16 | 5432 |
| `luminalib_ollama` | Llama 3 via Ollama | 11434 |
| `luminalib_ollama_init` | Pulls llama3 model (one-shot) | — |
| `luminalib_minio` | S3-compatible object storage | 9000, 9001 |
| `luminalib_minio_init` | Creates S3 bucket (one-shot) | — |
| `luminalib_api` | LuminaLib FastAPI app | **8000** |

> **First run note:** Ollama will download the Llama 3 model (~4.7 GB). This takes a few minutes depending on your connection. Subsequent starts are instant.

### 3. Verify

```bash
# API health / interactive docs
open http://localhost:8000/docs

# MinIO storage console
open http://localhost:9001   # user: minioadmin / pass: minioadmin
```

---

## 📖 API Reference

Full interactive documentation is available at **`http://localhost:8000/docs`** (Swagger UI).

### Authentication

```bash
# Register
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","username":"alice","password":"secret123"}'

# Login → get JWT
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"secret123"}'

# Response: {"access_token": "<JWT>", "token_type": "bearer"}
export TOKEN="<paste JWT here>"
```

### Books

```bash
# Upload a book (PDF or TXT) with metadata
curl -X POST http://localhost:8000/books \
  -H "Authorization: Bearer $TOKEN" \
  -F 'metadata={"title":"Dune","author":"Frank Herbert","genre":"sci-fi","tags":["sci-fi","epic","desert"]}' \
  -F 'file=@/path/to/dune.pdf'

# List books (paginated)
curl "http://localhost:8000/books?page=1&page_size=10&genre=sci-fi" \
  -H "Authorization: Bearer $TOKEN"

# Get a specific book (includes ai_summary once generated)
curl http://localhost:8000/books/<book_id> \
  -H "Authorization: Bearer $TOKEN"

# Update book metadata
curl -X PUT http://localhost:8000/books/<book_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":"A classic sci-fi novel about desert planets."}'

# Delete a book
curl -X DELETE http://localhost:8000/books/<book_id> \
  -H "Authorization: Bearer $TOKEN"

# Borrow a book
curl -X POST http://localhost:8000/books/<book_id>/borrow \
  -H "Authorization: Bearer $TOKEN"

# Return a book
curl -X POST http://localhost:8000/books/<book_id>/return \
  -H "Authorization: Bearer $TOKEN"
```

### Reviews & Analysis

```bash
# Submit a review (must have borrowed the book first)
curl -X POST http://localhost:8000/books/<book_id>/reviews \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rating": 5, "body": "A masterpiece of world-building and political intrigue."}'

# Get AI-aggregated review analysis
curl http://localhost:8000/books/<book_id>/analysis \
  -H "Authorization: Bearer $TOKEN"
```

### Recommendations

```bash
# Get personalized ML book recommendations
curl http://localhost:8000/recommendations \
  -H "Authorization: Bearer $TOKEN"
```

---

## ⚙️ Configuration Reference

All configuration is done via `.env`. No code changes needed to switch providers.

### Switch LLM Provider

```bash
# Use local Llama 3 (default)
LLM_BACKEND=ollama
OLLAMA_MODEL=llama3

# Use OpenAI GPT-4o-mini instead
LLM_BACKEND=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

### Switch Storage Backend

```bash
# Use local disk (default)
STORAGE_BACKEND=local

# Use MinIO / AWS S3
STORAGE_BACKEND=s3
S3_ENDPOINT_URL=http://minio:9000     # or https://s3.amazonaws.com for real AWS
S3_BUCKET_NAME=luminalib-books
S3_ACCESS_KEY=your_key
S3_SECRET_KEY=your_secret
```

### Switch Recommendation Algorithm

```bash
# Content-based filtering (default — works from first borrow)
RECOMMENDATION_ALGORITHM=content_based

# Collaborative filtering (better with many users)
RECOMMENDATION_ALGORITHM=collaborative
```

---

## 🏗️ Project Structure

```
luminalib/
├── app/
│   ├── api/
│   │   ├── dependencies.py        # JWT auth injection
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── books.py
│   │       ├── reviews.py
│   │       └── recommendations.py
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (env-driven)
│   │   ├── security.py            # JWT + bcrypt
│   │   └── exceptions.py          # Domain HTTP exceptions
│   ├── db/
│   │   ├── base.py                # SQLAlchemy declarative base
│   │   └── session.py             # Async engine + session factory
│   ├── models/
│   │   └── models.py              # ORM: User, Book, BookBorrow, Review, UserPreference
│   ├── schemas/
│   │   └── schemas.py             # Pydantic request/response models
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── book_service.py
│   │   ├── review_service.py
│   │   ├── llm/
│   │   │   ├── base.py            # BaseLLMService interface
│   │   │   ├── prompts.py         # Structured, reusable prompt templates
│   │   │   ├── ollama_service.py
│   │   │   ├── openai_service.py
│   │   │   └── factory.py
│   │   ├── storage/
│   │   │   ├── base.py            # BaseStorageService interface
│   │   │   ├── local_storage.py
│   │   │   ├── s3_storage.py
│   │   │   └── factory.py
│   │   └── ml/
│   │       └── recommendation_engine.py
│   ├── tasks/
│   │   └── background_tasks.py    # Async AI background processing
│   └── main.py                    # App factory + lifespan
├── tests/
│   ├── test_auth_service.py
│   ├── test_recommendation_engine.py
│   └── test_prompts.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml                 # ruff + mypy config
├── .env.example
├── ARCHITECTURE.md
└── README.md
```

---

## 🧪 Running Tests

```bash
# Install dev dependencies locally
pip install -r requirements.txt
pip install pytest pytest-asyncio aiosqlite

# Run all tests
pytest -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

---

## 🔍 Linting & Formatting

```bash
# Format and lint with ruff
ruff format app/ tests/
ruff check app/ tests/ --fix

# Type checking with mypy
mypy app/
```

---

## 🧠 How AI Summarization Works

1. **Book uploaded** → `POST /books` returns `201` immediately
2. `summary_status` starts as `"pending"`
3. **Background task** fires: downloads file → extracts text → sends to LLM
4. `summary_status` becomes `"processing"` then `"done"` (or `"failed"`)
5. Poll `GET /books/{id}` to check `summary_status` and read `ai_summary`

```
summary_status: "pending" → "processing" → "done"
                                         ↘ "failed"  (on LLM error)
```

---

## 🧠 How Review Consensus Works

1. **Review submitted** → `POST /books/{id}/reviews` returns `201` immediately
2. Background task fires and:
   - Labels each unlabeled review with a sentiment (`positive` / `neutral` / `negative`)
   - Re-synthesizes the rolling consensus across all reviews
3. View the result at `GET /books/{id}/analysis`

---

## 🔒 Security Notes

- Never commit `.env` to version control (it's in `.gitignore`)
- Rotate `SECRET_KEY` by generating a new `openssl rand -hex 32` value
- In production, set `POSTGRES_PASSWORD` to a strong random value
- File uploads are restricted to PDF and TXT only; keys are UUID-prefixed

---

## 🛠️ Production Considerations

| Concern | Current | Recommended for Prod |
|---------|---------|----------------------|
| Background tasks | `asyncio.create_task()` | Celery + Redis / ARQ |
| DB migrations | Auto-create on startup | Alembic versioned migrations |
| Token revocation | Stateless (no revocation) | Redis token denylist |
| Scaling | Single uvicorn worker | Gunicorn + multiple workers |
| LLM | Ollama (local) | Ollama with GPU / OpenAI |
| Storage | Local disk | AWS S3 (set `STORAGE_BACKEND=s3`) |

---

