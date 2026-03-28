# LuminaLib — Architecture Document

## Table of Contents
1. [System Overview](#1-system-overview)
2. [DB Schema Design: User Preferences](#2-db-schema-design-user-preferences)
3. [Async Strategy: LLM Generation](#3-async-strategy-llm-generation)
4. [ML Recommendation Strategy](#4-ml-recommendation-strategy)
5. [Provider Swappability (Storage & LLM)](#5-provider-swappability-storage--llm)
6. [Clean Architecture Layers](#6-clean-architecture-layers)
7. [Security Design](#7-security-design)
8. [Data Flow Diagrams](#8-data-flow-diagrams)

---

## 1. System Overview

LuminaLib is structured as a layered FastAPI application following **Clean Architecture** principles. Each layer has a single responsibility and communicates with adjacent layers via interfaces (abstract base classes), never concrete implementations.

```
┌─────────────────────────────────────────────┐
│              HTTP / FastAPI Layer            │  ← Routes, schemas, DI wiring
├─────────────────────────────────────────────┤
│              Service Layer                  │  ← Business logic (pure Python)
├─────────────────────────────────────────────┤
│         Infrastructure Interfaces           │  ← BaseLLMService, BaseStorageService
├─────────────────────────────────────────────┤
│     Concrete Providers (via factories)      │  ← Ollama/OpenAI, Local/S3, PostgreSQL
└─────────────────────────────────────────────┘
```

All cross-layer wiring happens in **factories** and **FastAPI dependency functions** — the service layer never instantiates a provider directly.

---

## 2. DB Schema Design: User Preferences

### Decision: Hybrid Explicit + Implicit Model

We chose a **hybrid preference model** rather than a purely explicit or purely implicit approach, because neither alone is sufficient for a good recommendation system:

| Approach | Pros | Cons |
|----------|------|------|
| Explicit only | User-controlled, interpretable | Cold-start; users rarely fill it in |
| Implicit only | Automatic, zero friction | Noisy; early borrows skew results |
| **Hybrid (chosen)** | Best of both; implicit fills cold-start gaps | Slightly more complex schema |

### Schema: `user_preferences` table

```sql
CREATE TABLE user_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- Explicit: tags the user voluntarily selects (e.g. ["sci-fi", "history"])
    explicit_tags       TEXT[],

    -- Implicit: tags accumulated from borrow history (union of borrowed book tags)
    implicit_tags       TEXT[],

    -- Implicit: rolling average rating given across all reviews
    avg_rating_given    FLOAT,

    -- Implicit: total lifetime borrows (useful for cold-start detection)
    total_books_borrowed INTEGER NOT NULL DEFAULT 0,

    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Tag Source: `books.tags` column

Books carry a `TEXT[]` tags column (e.g. `["dystopia", "sci-fi", "classic"]`). When a user borrows a book, the book's tags are unioned into `implicit_tags`. This means the preference vector updates automatically — no manual curation required.

### Why PostgreSQL Arrays?

- Tag sets are read-only during recommendation (no per-tag queries needed)
- Array overlap (`&&`) and containment (`@>`) operators enable future SQL-level filtering
- Avoids a separate `user_preference_tags` join table, keeping reads to a single row

### Why One Row Per User?

Preference vectors are read as a whole (for cosine similarity) and updated incrementally. A single-row model means O(1) reads and simple `UPDATE` semantics. If the preference model grows (e.g. per-genre rating vectors), this can be migrated to a separate `user_genre_ratings` table without breaking the interface.

---

## 3. Async Strategy: LLM Generation

### Problem

LLM inference (local Llama 3 via Ollama) can take **10–120 seconds**. Blocking an HTTP request for that duration would:
- Time out clients
- Exhaust the ASGI worker pool
- Make the API feel broken

### Chosen Solution: `asyncio.create_task()`

We use Python's native `asyncio.create_task()` to dispatch background coroutines from within the request handler, after the DB record has been flushed and the HTTP response has been returned.

```
POST /books  ──►  Book row created  ──►  HTTP 201 returned immediately
                       │
                       └──► asyncio.create_task(run_book_summarization(...))
                                  │  (runs concurrently, owns its own DB session)
                                  ▼
                            LLM generates summary
                                  │
                                  ▼
                            books.ai_summary updated
                            books.summary_status = "done"
```

The `summary_status` column (`pending → processing → done | failed`) allows clients to poll `GET /books/{id}` and check when the summary is ready.

### Why Not Celery/ARQ?

| Approach | Pro | Con |
|----------|-----|-----|
| `asyncio.create_task` | Zero infrastructure; works in dev and prod | Lost on process crash; no retry |
| **Celery + Redis** | Retries, distributed workers, monitoring | Requires Redis + Celery worker containers |
| **ARQ** | Async-native, lightweight | Less mature ecosystem |

For a **production deployment**, the background task function signatures are kept clean and stateless — they accept only IDs and interfaces, so they can be lifted into a Celery/ARQ task with minimal changes (wrap the coroutine body in a `@celery.task` or `@arq.task` decorator).

### DB Session Isolation

Each background task creates its **own `AsyncSession`** via `AsyncSessionFactory()`. This is critical: the request's session is committed and closed before the task reads back the book row.

---

## 4. ML Recommendation Strategy

### Two Algorithms (switchable via config)

#### A. Content-Based Filtering (default)

**Mechanism:** Cosine similarity between a user's preference tag vector and each book's tag vector.

```
User preference vector:  [1, 0, 1, 0, 1]   (sci-fi=1, romance=0, dystopia=1, ...)
Book A vector:           [1, 0, 1, 0, 0]
Book B vector:           [0, 1, 0, 1, 0]

cosine_sim(user, A) = 0.816  ← recommended
cosine_sim(user, B) = 0.0    ← not recommended
```

**Strengths:**
- Works from first borrow (implicit tags kick in immediately)
- No need for other users' data
- Fully explainable ("based on your interest in sci-fi, dystopia")

**Weaknesses:**
- Cannot surface serendipitous finds outside known tag space
- Quality depends on books being well-tagged

#### B. Collaborative Filtering (item-based)

**Mechanism:** "Users who borrowed the same books as you also borrowed these."

```
User A borrows: [Book1, Book2, Book3]
User B borrows: [Book1, Book2, Book4]  ← similar to A (overlap: Book1, Book2)
User C borrows: [Book1, Book5]         ← somewhat similar

Score(Book4) = 1  (borrowed by 1 similar user)
Score(Book5) = 1  (borrowed by 1 similar user)
→ Recommend Book4, Book5 to User A
```

**Strengths:**
- Discovers surprising recommendations across genre boundaries
- Improves as the dataset grows

**Weaknesses:**
- Cold-start: no recommendations until user has borrowed ≥ 1 book
- Requires other users with overlapping history

#### Cold-Start Handling

Both algorithms fall back to **"newest books"** when insufficient data exists.

### Switching Algorithms

```bash
# In .env:
RECOMMENDATION_ALGORITHM=collaborative   # or content_based
```

No code changes required.

---

## 5. Provider Swappability (Storage & LLM)

### The Interface Contract

```python
class BaseLLMService(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None) -> str: ...

class BaseStorageService(ABC):
    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str) -> str: ...
    @abstractmethod
    async def download(self, key: str) -> bytes: ...
    @abstractmethod
    async def delete(self, key: str) -> None: ...
```

Business logic (`BookService`, `ReviewService`, background tasks) only ever types against `BaseLLMService` and `BaseStorageService`. They never import `OllamaLLMService` or `LocalStorageService` directly.

### Factory Pattern

```python
# Swap LLM: change LLM_BACKEND=openai in .env
def get_llm_service(backend: str) -> BaseLLMService:
    if backend == "openai":
        return OpenAILLMService()
    return OllamaLLMService()      # default

# Swap Storage: change STORAGE_BACKEND=s3 in .env
def get_storage_service(backend: str) -> BaseStorageService:
    if backend == "s3":
        return S3StorageService()
    return LocalStorageService()   # default
```

### Adding a New Provider

To add, say, **Azure OpenAI**:
1. Create `app/services/llm/azure_openai_service.py` implementing `BaseLLMService`
2. Add `"azure"` case to `get_llm_service()`
3. Set `LLM_BACKEND=azure` in `.env`

Zero changes to routes, services, or background tasks.

---

## 6. Clean Architecture Layers

```
app/
├── api/              # HTTP boundary — routes, schemas, DI wiring
│   ├── routes/       # One file per domain
│   └── dependencies.py  # FastAPI Depends() — auth, session injection
│
├── services/         # Business logic — no FastAPI, no SQLAlchemy imports
│   ├── auth_service.py
│   ├── book_service.py
│   ├── review_service.py
│   ├── llm/          # LLM abstraction layer
│   │   ├── base.py        ← interface
│   │   ├── prompts.py     ← structured, versioned prompts
│   │   ├── ollama_service.py
│   │   ├── openai_service.py
│   │   └── factory.py
│   ├── storage/      # Storage abstraction layer
│   │   ├── base.py        ← interface
│   │   ├── local_storage.py
│   │   ├── s3_storage.py
│   │   └── factory.py
│   └── ml/
│       └── recommendation_engine.py
│
├── models/           # SQLAlchemy ORM models (DB schema)
├── schemas/          # Pydantic models (API contract)
├── db/               # Session factory, init
├── core/             # Config, security, exceptions
└── tasks/            # Background async tasks
```

### SOLID Principles Applied

| Principle | Implementation |
|-----------|---------------|
| **S**ingle Responsibility | Each service class has one job (AuthService handles only auth) |
| **O**pen/Closed | New LLM/storage providers extend without modifying existing code |
| **L**iskov Substitution | Any `BaseLLMService` subclass is drop-in replaceable |
| **I**nterface Segregation | Storage and LLM interfaces are minimal and separate |
| **D**ependency Inversion | Services depend on abstract interfaces, not concrete providers |

---

## 7. Security Design

### Password Hashing
- **bcrypt** via `passlib` with automatic salt generation
- Cost factor default (12 rounds) — suitable for production

### JWT Tokens
- **HS256** signed with `SECRET_KEY` (must be ≥ 32 random bytes)
- `exp` claim enforces expiry (default: 60 minutes)
- Stateless — no server-side session store needed for basic use
- For signout/revocation: add a Redis-backed token denylist (slot in `get_current_user` dependency)

### Borrow Gate on Reviews
Enforced in `ReviewService.submit_review()`:
```python
borrow = await db.execute(
    select(BookBorrow).where(
        BookBorrow.book_id == book_id,
        BookBorrow.user_id == user.id,
    )
)
if not borrow.scalar_one_or_none():
    raise ForbiddenError("You must borrow a book before reviewing it.")
```

### File Upload Safety
- Only `application/pdf` and `text/plain` content types accepted
- Storage key is UUID-prefixed — no user-supplied filenames in paths
- Directory traversal protection in `LocalStorageService._resolve()`

---

## 8. Data Flow Diagrams

### Book Ingestion Flow

```
Client
  │  POST /books (multipart: metadata JSON + file)
  ▼
BookRouter
  │  parse metadata, read file bytes
  ▼
BookService.create_book()
  │  validate file type
  │  storage.upload(key, bytes)      ← BaseStorageService
  │  INSERT into books               ← PostgreSQL
  │  asyncio.create_task(...)        ← fire-and-forget
  ▼
HTTP 201 ← returned to client immediately

(background)
run_book_summarization()
  │  storage.download(key)
  │  extract_text(bytes)
  │  llm.generate(SummarizationPrompt)   ← BaseLLMService
  │  UPDATE books SET ai_summary=...
  ▼
  done
```

### Review → Consensus Flow

```
Client
  │  POST /books/{id}/reviews  {"rating": 5, "body": "..."}
  ▼
ReviewService.submit_review()
  │  check borrow gate
  │  check duplicate review
  │  INSERT into reviews
  │  asyncio.create_task(run_review_consensus_update)
  ▼
HTTP 201 ← returned immediately

(background)
run_review_consensus_update()
  │  SELECT all reviews for book
  │  for each review without sentiment:
  │      llm.generate(SentimentPrompt)  → "positive"|"neutral"|"negative"
  │      UPDATE reviews SET sentiment=...
  │  llm.generate(ReviewConsensusPrompt, all_reviews)
  │  UPDATE books SET ai_review_consensus=...
  ▼
  done
```

### Recommendation Flow

```
Client
  │  GET /recommendations
  ▼
RecommendationEngine.recommend(user)
  │
  ├─ [content_based]
  │    SELECT user_preferences WHERE user_id=...
  │    merge explicit_tags + implicit_tags → user_vector
  │    SELECT all books → compute cosine_similarity per book
  │    sort desc → top N
  │
  └─ [collaborative]
       SELECT all book_borrows
       build user→books map
       find similar users (overlap with current user's borrows)
       score candidate books by co-borrower count
       sort desc → top N
  ▼
HTTP 200 [{books}, algorithm, based_on]
```
